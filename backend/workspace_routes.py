import hashlib
import hmac
import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core import db, now, new_id, get_current_user, get_owned_client, FREE_PAGE_LIMIT, PAID_PLANS
import ledger_engine as le
import textract_pipeline as tp

router = APIRouter(prefix="/api", tags=["workspace"])
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
LIST_PROJECTION = {"_id": 0, "rows": 0}


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    industry: str = Field(default="", max_length=80)
    contact_email: str = Field(default="", max_length=160)
    platforms: List[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1000)


class RowIn(BaseModel):
    id: str
    date: str
    description: str = ""
    reference: str = ""
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    balance: Optional[float] = None


class RowsIn(BaseModel):
    rows: List[RowIn]


class RateIn(BaseModel):
    commission_rate: float = Field(ge=0, le=100)


def _clean_client(body: ClientIn) -> dict:
    data = body.model_dump()
    data["name"] = data["name"].strip()
    data["platforms"] = [p for p in data["platforms"] if p in le.PLATFORMS]
    return data


async def _read_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit")
    return raw


# ---------- Clients ----------
@router.get("/clients")
async def list_clients(user: dict = Depends(get_current_user)):
    owner = user["user_id"]
    clients = await db.clients.find({"owner_id": owner}, {"_id": 0}).sort("created_at", -1).to_list(500)
    stats = {}
    async for s in db.statements.aggregate([
        {"$match": {"owner_id": owner}},
        {"$group": {"_id": "$client_id", "statements": {"$sum": 1}, "pages": {"$sum": "$pages"}}},
    ]):
        stats[s["_id"]] = {"statements": s["statements"], "pages": s["pages"]}
    payouts = {}
    async for p in db.payouts.aggregate([
        {"$match": {"owner_id": owner}}, {"$group": {"_id": "$client_id", "n": {"$sum": 1}}},
    ]):
        payouts[p["_id"]] = p["n"]
    for c in clients:
        st = stats.get(c["id"], {})
        c["statements_count"] = st.get("statements", 0)
        c["pages_converted"] = st.get("pages", 0)
        c["payouts_count"] = payouts.get(c["id"], 0)
    return clients


@router.post("/clients")
async def create_client(body: ClientIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id("cli"), "owner_id": user["user_id"], **_clean_client(body), "created_at": now().isoformat()}
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/clients/{client_id}")
async def update_client(client_id: str, body: ClientIn, user: dict = Depends(get_current_user)):
    await get_owned_client(user["user_id"], client_id)
    data = _clean_client(body)
    await db.clients.update_one({"id": client_id, "owner_id": user["user_id"]}, {"$set": data})
    await db.statements.update_many({"client_id": client_id, "owner_id": user["user_id"]}, {"$set": {"client_name": data["name"]}})
    await db.payouts.update_many({"client_id": client_id, "owner_id": user["user_id"]}, {"$set": {"client_name": data["name"]}})
    return await get_owned_client(user["user_id"], client_id)


@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, user: dict = Depends(get_current_user)):
    await get_owned_client(user["user_id"], client_id)
    await db.clients.delete_one({"id": client_id, "owner_id": user["user_id"]})
    return {"ok": True}


# ---------- Bank Statement Converter ----------
@router.get("/statements/engine")
async def statement_engine(user: dict = Depends(get_current_user)):
    return {"engine": "aws_textract", "configured": tp.textract_enabled(), "region": os.environ.get("AWS_REGION", "")}


@router.post("/statements")
async def convert_statement(
    file: UploadFile = File(...), client_id: str = Form(...), user: dict = Depends(get_current_user),
):
    client = await get_owned_client(user["user_id"], client_id)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF bank statements are supported")
    if not tp.textract_enabled():
        raise HTTPException(
            status_code=503,
            detail="Amazon Textract is not connected yet. Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_REGION to enable PDF parsing.",
        )
    raw = await _read_upload(file)
    try:
        pages = await run_in_threadpool(tp.count_pages, raw)
    except Exception:
        raise HTTPException(status_code=400, detail="This file is not a readable PDF")
    query = {"user_id": user["user_id"]}
    if user.get("plan") not in PAID_PLANS:
        query["pages_used"] = {"$lte": FREE_PAGE_LIMIT - pages}
    reserved = await db.users.update_one(query, {"$inc": {"pages_used": pages}})
    if reserved.matched_count == 0:
        remaining = max(FREE_PAGE_LIMIT - user.get("pages_used", 0), 0)
        raise HTTPException(
            status_code=402,
            detail=f"Free trial limit reached: this statement has {pages} page(s) and you have {remaining} of {FREE_PAGE_LIMIT} free pages left. Upgrade to continue.",
        )
    try:
        rows = await run_in_threadpool(tp.run_pipeline, raw)
    except Exception as e:
        await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"pages_used": -pages}})
        logger.exception("Textract pipeline failed")
        reason = str(e) if isinstance(e, (tp.TextractError, tp.TextractNotConfigured)) else "Statement parsing failed"
        raise HTTPException(status_code=502, detail=f"{reason}. Your pages were not charged.")
    doc = {
        "id": new_id("stm"), "kind": "statement", "owner_id": user["user_id"],
        "client_id": client["id"], "client_name": client["name"], "filename": file.filename,
        "pages": pages, "engine": "aws_textract", "status": "completed", "rows": rows,
        "summary": tp.summarize(rows), "created_at": now().isoformat(),
    }
    await db.statements.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _owned_statement(user: dict, statement_id: str) -> dict:
    doc = await db.statements.find_one({"id": statement_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Statement not found")
    return doc


@router.get("/statements/{statement_id}")
async def get_statement(statement_id: str, user: dict = Depends(get_current_user)):
    return await _owned_statement(user, statement_id)


@router.put("/statements/{statement_id}/rows")
async def save_rows(statement_id: str, body: RowsIn, user: dict = Depends(get_current_user)):
    await _owned_statement(user, statement_id)
    rows = [r.model_dump() for r in body.rows]
    for r in rows:
        for k in tp.AMOUNT_COLUMNS:
            r[k] = float(tp.d2(r[k])) if r[k] is not None else None
    await db.statements.update_one(
        {"id": statement_id, "owner_id": user["user_id"]},
        {"$set": {"rows": rows, "summary": tp.summarize(rows), "updated_at": now().isoformat()}},
    )
    return await _owned_statement(user, statement_id)


@router.get("/statements/{statement_id}/export")
async def export_statement(statement_id: str, fmt: str = "csv", user: dict = Depends(get_current_user)):
    doc = await _owned_statement(user, statement_id)
    fmt = "xlsx" if fmt == "xlsx" else "csv"
    content = await run_in_threadpool(tp.rows_to_export, doc["rows"], fmt)
    base = doc["filename"].rsplit(".", 1)[0]
    media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{base}_ledger.{fmt}"'})


@router.post("/webhooks/textract")
async def textract_webhook(request: Request):
    """Secure connector for async Textract jobs: body {statement_id, Blocks:[...]}, HMAC-SHA256 signed."""
    body = await request.body()
    secret = os.environ["TEXTRACT_WEBHOOK_SECRET"].encode()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-LedgerStream-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(body)
        statement_id, blocks = payload["statement_id"], payload["Blocks"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Expected JSON with statement_id and Blocks")
    doc = await db.statements.find_one({"id": statement_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Statement not found")
    rows = tp.dataframe_to_rows(tp.blocks_to_dataframe(blocks))
    await db.statements.update_one({"id": statement_id}, {"$set": {
        "rows": rows, "summary": tp.summarize(rows), "engine": "aws_textract",
        "status": "completed", "updated_at": now().isoformat(),
    }})
    return {"ok": True, "transactions": len(rows)}


# ---------- Merchant Payout Splitter ----------
@router.get("/payouts/sample/{platform}")
async def sample_payout_csv(platform: str, user: dict = Depends(get_current_user)):
    if platform not in le.SAMPLE_CSV:
        raise HTTPException(status_code=404, detail="Unknown platform")
    return Response(le.SAMPLE_CSV[platform], media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sample_{platform}_payout.csv"'})


@router.post("/payouts")
async def split_payout(
    file: UploadFile = File(...), client_id: str = Form(...), platform: str = Form(...),
    commission_rate: float = Form(30.0), user: dict = Depends(get_current_user),
):
    client = await get_owned_client(user["user_id"], client_id)
    if platform not in le.PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    if not 0 <= commission_rate <= 100:
        raise HTTPException(status_code=400, detail="Commission rate must be between 0 and 100")
    raw = await _read_upload(file)
    try:
        parsed = await run_in_threadpool(le.parse_platform_csv, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    doc = {
        "id": new_id("pay"), "kind": "payout", "owner_id": user["user_id"],
        "client_id": client["id"], "client_name": client["name"], "platform": platform,
        "filename": file.filename, **parsed, "commission_rate": commission_rate,
        "ledger": le.build_ledger(parsed["gross_total"], commission_rate), "created_at": now().isoformat(),
    }
    await db.payouts.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _owned_payout(user: dict, payout_id: str) -> dict:
    doc = await db.payouts.find_one({"id": payout_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout not found")
    return doc


@router.get("/payouts/{payout_id}")
async def get_payout(payout_id: str, user: dict = Depends(get_current_user)):
    return await _owned_payout(user, payout_id)


@router.post("/payouts/{payout_id}/recalculate")
async def recalculate_payout(payout_id: str, body: RateIn, user: dict = Depends(get_current_user)):
    doc = await _owned_payout(user, payout_id)
    ledger = le.build_ledger(doc["gross_total"], body.commission_rate)
    await db.payouts.update_one({"id": payout_id, "owner_id": user["user_id"]},
                                {"$set": {"commission_rate": body.commission_rate, "ledger": ledger}})
    return {**doc, "commission_rate": body.commission_rate, "ledger": ledger}


@router.get("/payouts/{payout_id}/qbo")
async def payout_qbo_csv(payout_id: str, user: dict = Depends(get_current_user)):
    doc = await _owned_payout(user, payout_id)
    return Response(le.ledger_to_qbo_csv(doc), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="qbo_journal_{doc["platform"]}_{payout_id[-6:]}.csv"'})


# ---------- History & Dashboard ----------
@router.get("/history")
async def history(client_id: Optional[str] = None, kind: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {"owner_id": user["user_id"]}
    if client_id:
        query["client_id"] = client_id
    items = []
    if kind == "needs_review":
        return await db.statements.find(
            {**query, "summary.reconciliation.status": "mismatch"}, LIST_PROJECTION
        ).sort("created_at", -1).to_list(1000)
    if kind in (None, "statement"):
        items += await db.statements.find(query, LIST_PROJECTION).to_list(1000)
    if kind in (None, "payout"):
        items += await db.payouts.find(query, LIST_PROJECTION).to_list(1000)
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


@router.get("/history/review-count")
async def review_count(user: dict = Depends(get_current_user)):
    n = await db.statements.count_documents({"owner_id": user["user_id"], "summary.reconciliation.status": "mismatch"})
    return {"needs_review": n}


@router.delete("/history/{kind}/{item_id}")
async def delete_history(kind: str, item_id: str, user: dict = Depends(get_current_user)):
    coll = {"statement": db.statements, "payout": db.payouts}.get(kind)
    if coll is None:
        raise HTTPException(status_code=404, detail="Not found")
    res = await coll.delete_one({"id": item_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    owner = {"owner_id": user["user_id"]}
    txn = 0
    async for s in db.statements.aggregate([{"$match": owner}, {"$group": {"_id": None, "t": {"$sum": "$summary.transactions"}}}]):
        txn = s["t"]
    return {
        "clients": await db.clients.count_documents(owner),
        "statements": await db.statements.count_documents(owner),
        "payouts": await db.payouts.count_documents(owner),
        "transactions_extracted": txn,
    }
