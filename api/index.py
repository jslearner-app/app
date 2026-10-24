"""Standalone serverless processing API for LedgerStream AI (statements, payouts, reconciliation)."""
import hmac
import os
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from ledgerstream_core import payouts, reconciliation, statements
from ledgerstream_core.schemas import StatementRows

app = FastAPI(title="LedgerStream AI Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


def require_api_key(x_api_key: str = Header(default="")):
    expected = os.environ.get("LEDGERSTREAM_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="LEDGERSTREAM_API_KEY is not configured")
    if not hmac.compare_digest(expected, x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


async def _read(file: UploadFile, ext: str) -> bytes:
    if not (file.filename or "").lower().endswith(ext):
        raise HTTPException(status_code=400, detail=f"Expected a {ext} file")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(raw) > statements.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit")
    return raw


@app.get("/api/health")
async def health():
    return {"status": "ok", "textract_configured": statements.textract_enabled()}


@app.post("/api/statements/convert", dependencies=[Depends(require_api_key)])
async def convert_statement(file: UploadFile = File(...)):
    raw = await _read(file, ".pdf")
    try:
        pages = await run_in_threadpool(statements.count_pages, raw)
    except Exception:
        raise HTTPException(status_code=400, detail="This file is not a readable PDF")
    try:
        rows = await run_in_threadpool(statements.run_pipeline, raw)
    except statements.TextractNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except statements.TextractError as e:
        raise HTTPException(status_code=424, detail=str(e))
    return {"filename": file.filename, "pages": pages, "rows": rows, "summary": reconciliation.summarize(rows)}


@app.post("/api/statements/reconcile", dependencies=[Depends(require_api_key)])
async def reconcile_rows(body: StatementRows):
    rows = reconciliation.normalize_rows([r.model_dump() for r in body.rows])
    return reconciliation.summarize(rows)


@app.post("/api/payouts/split", dependencies=[Depends(require_api_key)])
async def split_payout(
    file: UploadFile = File(...), platform: str = Form(...), commission_rate: float = Form(30.0),
    client_name: str = Form(""), format: str = Form("json"),
):
    if platform not in payouts.PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    if not 0 <= commission_rate <= 100:
        raise HTTPException(status_code=400, detail="Commission rate must be between 0 and 100")
    raw = await _read(file, ".csv")
    try:
        parsed = await run_in_threadpool(payouts.parse_platform_csv, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = {
        "id": uuid.uuid4().hex, "platform": platform, "filename": file.filename, "client_name": client_name,
        **parsed, "commission_rate": commission_rate,
        "ledger": payouts.build_ledger(parsed["gross_total"], commission_rate, platform),
    }
    if format == "qbo":
        return Response(payouts.ledger_to_qbo_csv(result), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="qbo_journal_{platform}.csv"'})
    return result
