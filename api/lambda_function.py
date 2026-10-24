"""LedgerStream AI - standalone serverless backend (AWS Lambda via Mangum, Vercel, or any ASGI host)."""
import hashlib
import hmac
import io
import ipaddress
import json
import logging
import os
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from html.parser import HTMLParser
from typing import List, Literal, Optional
from urllib.parse import urlparse

import bcrypt
import boto3
import httpx
import jwt
import pandas as pd
import stripe
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from mangum import Mangum
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, field_validator
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from starlette.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ledgerstream")


# =====================================================================
# Configuration & database (DATABASE_URL = MongoDB connection string)
# =====================================================================
def _connect_database():
    mongo = AsyncIOMotorClient(os.environ["DATABASE_URL"])
    return mongo, mongo.get_default_database(os.environ.get("DB_NAME"))


client, db = _connect_database()

JWT_ALGORITHM = "HS256"
COOKIE_OPTS = dict(httponly=True, secure=True, samesite="none", path="/")
FREE_PAGE_LIMIT = 5
PAID_PLANS = {"starter", "agency"}
PLAN_PAGE_LIMITS = {"free": FREE_PAGE_LIMIT, "starter": 200, "agency": 1000}
LOW_PAGE_THRESHOLD = Decimal("0.8")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
CENT = Decimal("0.01")

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
STRIPE_TAX_MODE = "full"
PLAN_LOOKUP = {"starter": "starter_monthly", "agency": "agency_monthly"}

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_RAW_ORIGINS = [o.strip().rstrip("/") for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
if "*" in _RAW_ORIGINS:
    logger.warning("CORS_ORIGINS='*' is ignored: list the exact frontend origins instead")
ALLOWED_ORIGINS = [o for o in _RAW_ORIGINS if o != "*"]


def now():
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def d2(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


# =====================================================================
# Auth helpers (JWT cookies + Google session tokens)
# =====================================================================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": now() + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": now() + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def set_auth_cookies(response, user_id: str, email: str) -> str:
    refresh_token = create_refresh_token(user_id)
    response.set_cookie("access_token", create_access_token(user_id, email), max_age=900, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh_token, max_age=604800, **COOKIE_OPTS)
    return refresh_token


# ---------- CSRF: token = HMAC of the long-lived session cookie, sent back in X-CSRF-Token ----------
CSRF_COOKIES = ("refresh_token", "session_token")
CSRF_EXEMPT = ("/api/auth/login", "/api/auth/register", "/api/auth/google/session", "/api/auth/forgot-password",
               "/api/auth/reset-password", "/api/auth/refresh", "/api/auth/logout", "/api/webhooks/", "/api/stripe/webhook")


def csrf_token_for(base: str) -> str:
    return hmac.new(_jwt_secret().encode(), f"csrf:{base}".encode(), hashlib.sha256).hexdigest()


def request_csrf_token(request: Request):
    bases = [request.cookies[n] for n in CSRF_COOKIES if request.cookies.get(n)]
    return csrf_token_for(bases[0]) if bases else None


def csrf_valid(request: Request) -> bool:
    sent = request.headers.get("X-CSRF-Token", "")
    return any(hmac.compare_digest(sent, csrf_token_for(request.cookies[n])) for n in CSRF_COOKIES if request.cookies.get(n))


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


async def throttle(request: Request, scope: str, limit: int, window_minutes: int = 60):
    key = f"{scope}:{client_ip(request)}"
    if await db.rate_limits.count_documents({"key": key, "created_at": {"$gte": now() - timedelta(minutes=window_minutes)}}) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    await db.rate_limits.insert_one({"key": key, "created_at": now()})


def trusted_origin(url: str, request: Request) -> str:
    """Only our own frontends may be used as Stripe/email return addresses."""
    origin = (url or "").rstrip("/")
    parsed = urlparse(origin)
    same_host = parsed.scheme == "https" and parsed.netloc in (
        request.headers.get("x-forwarded-host"), request.headers.get("host"))
    if origin in ALLOWED_ORIGINS or same_host:
        return origin
    raise HTTPException(status_code=400, detail="Unrecognised app address")


def _as_utc(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _user_from_session(token: str):
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session or _as_utc(session["expires_at"]) < now():
        return None
    return await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})


async def _user_from_jwt(token: str):
    try:
        payload = decode_token(token, "access")
    except jwt.InvalidTokenError:
        return None
    return await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})


async def get_current_user(request: Request) -> dict:
    bearer = request.headers.get("Authorization", "")
    bearer = bearer[7:] if bearer.startswith("Bearer ") else None
    user = None
    access = request.cookies.get("access_token") or bearer
    if access:
        user = await _user_from_jwt(access)
    session = request.cookies.get("session_token") or bearer
    if not user and session:
        user = await _user_from_session(session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_owned_client(owner_id: str, client_id: str) -> dict:
    doc = await db.clients.find_one({"id": client_id, "owner_id": owner_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Client not found")
    return doc


# =====================================================================
# Monthly page counting, caps and the 80% low-page alert
# =====================================================================
def current_period() -> str:
    return now().strftime("%Y-%m")


def next_period_start() -> str:
    n = now()
    return (datetime(n.year + (n.month == 12), n.month % 12 + 1, 1, tzinfo=timezone.utc)).date().isoformat()


def page_limit(u: dict) -> int:
    return PLAN_PAGE_LIMITS.get(u.get("plan", "free"), FREE_PAGE_LIMIT)


def usage_pages(u: dict) -> int:
    """Lifetime pages for the free trial; current UTC calendar month for paid plans."""
    if u.get("plan") not in PAID_PLANS:
        return u.get("pages_used", 0)
    return u.get("period_pages", 0) if u.get("usage_period") == current_period() else 0


def low_page_alert(u: dict) -> bool:
    limit = page_limit(u)
    return bool(limit) and usage_pages(u) >= limit * LOW_PAGE_THRESHOLD


async def reserve_pages(u: dict, pages: int) -> bool:
    """Atomically books pages against the plan limit; False when the limit would be exceeded."""
    limit = page_limit(u)
    if u.get("plan") not in PAID_PLANS:
        res = await db.users.update_one(
            {"user_id": u["user_id"], "pages_used": {"$lte": limit - pages}}, {"$inc": {"pages_used": pages}})
        return res.modified_count == 1
    period = current_period()
    await db.users.update_one({"user_id": u["user_id"], "usage_period": {"$ne": period}},
                              {"$set": {"usage_period": period, "period_pages": 0}})
    res = await db.users.update_one(
        {"user_id": u["user_id"], "usage_period": period, "period_pages": {"$lte": limit - pages}},
        {"$inc": {"period_pages": pages, "pages_used": pages}})
    return res.modified_count == 1


async def release_pages(u: dict, pages: int):
    await db.users.update_one({"user_id": u["user_id"]}, {"$inc": {"pages_used": -pages}})
    if u.get("plan") in PAID_PLANS:
        await db.users.update_one(
            {"user_id": u["user_id"], "usage_period": current_period(), "period_pages": {"$gte": pages}},
            {"$inc": {"period_pages": -pages}})


def page_limit_message(u: dict, pages: int) -> str:
    limit = page_limit(u)
    remaining = max(limit - usage_pages(u), 0)
    if u.get("plan") in PAID_PLANS:
        return (f"Monthly page limit reached: your {u['plan'].title()} plan includes {limit} pages per month and "
                f"{remaining} are left, but this statement has {pages} page(s). The allowance resets on {next_period_start()}.")
    return (f"Free trial limit reached: this statement has {pages} page(s) and you have {remaining} of "
            f"{limit} free pages left. Upgrade to continue.")


def public_user(u: dict) -> dict:
    plan = u.get("plan", "free")
    return {
        "user_id": u["user_id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "firm_name": u.get("firm_name", ""),
        "picture": u.get("picture"),
        "auth_provider": u.get("auth_provider", "password"),
        "plan": plan,
        "subscription_status": u.get("subscription_status", "active_subscriber" if plan in PAID_PLANS else "trial"),
        "pages_used": u.get("pages_used", 0),
        "usage_pages": usage_pages(u),
        "page_limit": page_limit(u),
        "low_page_alert": low_page_alert(u),
        "limit_period": "month" if plan in PAID_PLANS else "trial",
        "period_resets_at": next_period_start() if plan in PAID_PLANS else None,
    }


# =====================================================================
# Bank statement pipeline: PDF -> AWS Textract (TABLES) -> Pandas -> rows
# =====================================================================
STATEMENT_COLUMNS = ["date", "description", "reference", "withdrawal", "deposit", "balance"]
EXPORT_HEADERS = ["Date", "Description", "Reference/Check #", "Withdrawals", "Deposits", "Balance"]
AMOUNT_COLUMNS = ["withdrawal", "deposit", "balance"]
COLUMN_KEYWORDS = [
    ("balance", ("balance",)),
    ("withdrawal", ("withdraw", "debit", "payments", "charges")),
    ("deposit", ("deposit", "credit")),
    ("reference", ("ref", "check", "chk", "cheque")),
    ("date", ("date", "posted")),
    ("description", ("description", "details", "transaction", "memo", "payee")),
]


class TextractNotConfigured(Exception):
    pass


class TextractError(Exception):
    pass


def count_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def textract_config() -> dict:
    return {
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "region_name": os.environ.get("AWS_REGION", ""),
    }


def textract_enabled() -> bool:
    values = textract_config().values()
    return all(values) and not any(v.startswith("AWS_PLACEHOLDER") for v in values)


def textract_client():
    if not textract_enabled():
        raise TextractNotConfigured("AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_REGION must be set")
    return boto3.client("textract", config=Config(retries={"max_attempts": 4, "mode": "standard"}), **textract_config())


def _split_pages(pdf_bytes: bytes):
    """Synchronous AnalyzeDocument accepts single-page PDFs, so each page is sent on its own."""
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        writer = PdfWriter()
        writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        yield buf.getvalue()


def analyze_with_textract(pdf_bytes: bytes) -> list:
    textract = textract_client()
    blocks = []
    for page_no, page_bytes in enumerate(_split_pages(pdf_bytes), start=1):
        try:
            resp = textract.analyze_document(Document={"Bytes": page_bytes}, FeatureTypes=["TABLES"])
        except ClientError as e:
            err = e.response.get("Error", {})
            if "service control policy" in (err.get("Message") or ""):
                raise TextractError(
                    "Amazon Textract is blocked by your AWS Organization: a service control policy explicitly denies "
                    "textract:AnalyzeDocument for this AWS user. An administrator of the AWS management account must "
                    "remove that deny (or move this account out of the policy) before statements can be converted")
            raise TextractError(f"Textract rejected page {page_no}: {err.get('Code')} - {err.get('Message')}")
        except BotoCoreError as e:
            raise TextractError(f"Could not reach Amazon Textract: {e}")
        for block in resp["Blocks"]:
            block["Page"] = page_no
            blocks.append(block)
    return blocks


def _child_ids(block: dict):
    for rel in block.get("Relationships", []) or []:
        if rel.get("Type") == "CHILD":
            yield from rel.get("Ids", [])


def _map_columns(headers) -> dict:
    mapping, used = {}, set()
    for header in headers:
        h = str(header).strip().lower()
        for canonical, keywords in COLUMN_KEYWORDS:
            if canonical not in used and any(k in h for k in keywords):
                mapping[header] = canonical
                used.add(canonical)
                break
    return mapping


def parse_amount(value):
    if value is None:
        return None
    s = str(value).strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s or s in {"-", "—"}:
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        amount = d2(s)
    except Exception:
        return None
    return float(-amount if negative else amount)


def blocks_to_dataframe(blocks: list) -> pd.DataFrame:
    by_id = {b["Id"]: b for b in blocks if "Id" in b}
    frames = []
    for table in (b for b in blocks if b.get("BlockType") == "TABLE"):
        grid = {}
        for cid in _child_ids(table):
            cell = by_id.get(cid)
            if not cell or cell.get("BlockType") != "CELL":
                continue
            words = [by_id[w]["Text"] for w in _child_ids(cell) if by_id.get(w, {}).get("BlockType") == "WORD"]
            grid[(cell["RowIndex"], cell["ColumnIndex"])] = " ".join(words)
        if not grid:
            continue
        n_rows = max(r for r, _ in grid)
        n_cols = max(c for _, c in grid)
        matrix = [[grid.get((r, c), "") for c in range(1, n_cols + 1)] for r in range(1, n_rows + 1)]
        df = pd.DataFrame(matrix[1:], columns=matrix[0])
        mapping = _map_columns(df.columns)
        if "date" not in mapping.values() or "description" not in mapping.values():
            continue
        frames.append(df[list(mapping.keys())].rename(columns=mapping))
    if not frames:
        return pd.DataFrame(columns=STATEMENT_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    for col in STATEMENT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[STATEMENT_COLUMNS]
    df["date"] = df["date"].astype(str).str.strip()
    df = df[df["date"] != ""]
    for col in AMOUNT_COLUMNS:
        df[col] = df[col].map(parse_amount).astype(object)
    df = df.astype(object).where(pd.notna(df), None)
    return df.reset_index(drop=True)


def dataframe_to_rows(df: pd.DataFrame) -> list:
    rows = []
    for rec in df.to_dict("records"):
        rec["id"] = uuid.uuid4().hex[:10]
        rec["reference"] = rec.get("reference") or ""
        rec["description"] = rec.get("description") or ""
        rows.append(rec)
    return rows


def run_statement_pipeline(pdf_bytes: bytes) -> list:
    return dataframe_to_rows(blocks_to_dataframe(analyze_with_textract(pdf_bytes)))


# ---------- Textract end-to-end connection check (sample statement, no pages charged) ----------
DIAG_HEADER = ["Date", "Description", "Reference", "Withdrawals", "Deposits", "Balance"]
DIAG_ROWS = [
    ["09/01/2026", "Opening deposit", "", "", "1,000.00", "1,000.00"],
    ["09/02/2026", "Office supplies", "1001", "150.25", "", "849.75"],
    ["09/03/2026", "Client payment", "", "", "420.00", "1,269.75"],
]
DIAG_COOLDOWN_SECONDS = 30


def build_sample_statement_pdf() -> bytes:
    buf = io.BytesIO()
    table = Table([DIAG_HEADER, *DIAG_ROWS])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    SimpleDocTemplate(buf, pagesize=letter).build(
        [Paragraph("LedgerStream Diagnostic Bank - Sample Statement", getSampleStyleSheet()["Title"]), table])
    return buf.getvalue()


def _textract_failure(e: ClientError):
    err = e.response.get("Error", {})
    code, msg = err.get("Code", ""), err.get("Message", "")
    if "service control policy" in msg:
        return "scp_blocked", ("Your AWS Organization's service control policy explicitly denies textract:AnalyzeDocument. "
                                "An administrator of the AWS management account must remove that deny.")
    if code == "AccessDeniedException":
        return "iam_denied", ("This AWS user has no permission for textract:AnalyzeDocument. Attach the "
                               "AmazonTextractFullAccess policy or allow textract:AnalyzeDocument.")
    if code in ("UnrecognizedClientException", "InvalidSignatureException"):
        return "invalid_keys", "AWS rejected these keys. Check the access key ID and secret."
    if code == "SubscriptionRequiredException":
        return "not_subscribed", "Amazon Textract isn't enabled for this AWS account yet."
    return "textract_error", f"{code}: {msg}"


def run_textract_diagnostic() -> dict:
    steps = []

    def step(key, label, ok, detail):
        steps.append({"id": key, "label": label, "ok": ok, "detail": detail})

    configured = textract_enabled()
    step("config", "AWS keys configured", configured, "Access key, secret and region are set" if configured
         else "Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_REGION")
    if not configured:
        return {"status": "not_configured", "steps": steps}
    cfg = textract_config()
    try:
        arn = boto3.client("sts", **cfg).get_caller_identity()["Arn"]
        step("credentials", "AWS credentials valid", True, f"Signed in as {arn.split(':')[-1].split('/')[-1]}")
    except (ClientError, BotoCoreError):
        step("credentials", "AWS credentials valid", False, "AWS rejected these keys. Check the access key ID and secret.")
        return {"status": "invalid_keys", "steps": steps}
    try:
        blocks = textract_client().analyze_document(
            Document={"Bytes": build_sample_statement_pdf()}, FeatureTypes=["TABLES"])["Blocks"]
    except ClientError as e:
        status, detail = _textract_failure(e)
        step("textract", "Textract access allowed", False, detail)
        return {"status": status, "steps": steps}
    except BotoCoreError as e:
        step("textract", "Textract access allowed", False, f"Could not reach Amazon Textract in {cfg['region_name']}: {e}")
        return {"status": "unreachable", "steps": steps}
    step("textract", "Textract access allowed", True, f"Amazon Textract answered in {cfg['region_name']}")
    rows = dataframe_to_rows(blocks_to_dataframe(blocks))
    rec = reconcile(rows)
    ok = len(rows) == len(DIAG_ROWS) and rec["status"] == "reconciled"
    step("pipeline", "Sample statement parsed and reconciled", ok,
         f"{len(rows)} of {len(DIAG_ROWS)} transactions extracted, reconciliation: {rec['status']}")
    return {"status": "ready" if ok else "parse_mismatch", "steps": steps}


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """Neutralises spreadsheet formula injection in exported text cells."""
    return f"'{value}" if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES) else value


def rows_to_export(rows: list, fmt: str) -> bytes:
    df = pd.DataFrame(rows, columns=STATEMENT_COLUMNS)
    for col in ("date", "description", "reference"):
        df[col] = df[col].map(safe_cell)
    df.columns = EXPORT_HEADERS
    if fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, sheet_name="Transactions", engine="openpyxl")
        return buf.getvalue()
    return df.to_csv(index=False, float_format="%.2f").encode("utf-8")


# ---------- Running-balance reconciliation ("Needs Review") ----------
def _row_net(row) -> Decimal:
    return (d2(row["deposit"]) if row.get("deposit") is not None else Decimal("0")) - (
        d2(row["withdrawal"]) if row.get("withdrawal") is not None else Decimal("0"))


def reconcile(rows: list) -> dict:
    """Checks opening balance + deposits - withdrawals against each printed running balance and the closing balance."""
    first = next((i for i, r in enumerate(rows) if r.get("balance") is not None), None)
    if first is None:
        return {"status": "unavailable", "message": "No running balance column was found on this statement."}
    opening = d2(rows[first]["balance"]) - _row_net(rows[first])
    for r in rows[:first]:
        opening -= _row_net(r)
    running, mismatches = opening, []
    for idx, r in enumerate(rows):
        running += _row_net(r)
        if r.get("balance") is None:
            continue
        printed = d2(r["balance"])
        if printed != running:
            mismatches.append({"id": r["id"], "row": idx + 1, "date": r.get("date", ""),
                               "expected": float(running), "actual": float(printed),
                               "difference": float(printed - running)})
            running = printed
    computed_closing = opening + sum((_row_net(r) for r in rows), Decimal("0"))
    reported_closing = d2(next(r["balance"] for r in reversed(rows) if r.get("balance") is not None))
    return {
        "status": "mismatch" if mismatches or computed_closing != reported_closing else "reconciled",
        "opening_balance": float(opening),
        "computed_closing": float(computed_closing),
        "reported_closing": float(reported_closing),
        "difference": float(reported_closing - computed_closing),
        "mismatched_rows": mismatches,
    }


def summarize(rows: list) -> dict:
    withdrawals = sum((d2(r["withdrawal"]) for r in rows if r.get("withdrawal") is not None), Decimal("0"))
    deposits = sum((d2(r["deposit"]) for r in rows if r.get("deposit") is not None), Decimal("0"))
    balances = [r["balance"] for r in rows if r.get("balance") is not None]
    return {
        "transactions": len(rows),
        "total_withdrawals": float(withdrawals),
        "total_deposits": float(deposits),
        "closing_balance": balances[-1] if balances else None,
        "reconciliation": reconcile(rows),
    }


def normalize_rows(rows: list) -> list:
    for r in rows:
        for k in AMOUNT_COLUMNS:
            r[k] = float(d2(r[k])) if r.get(k) is not None else None
    return rows


# =====================================================================
# Merchant payout splitter (Toast, DoorDash, UberEats, Shopify, Stripe, LawPay)
# =====================================================================
PLATFORMS = ["toast", "doordash", "ubereats", "shopify", "stripe", "lawpay"]
PLATFORM_NAMES = {"toast": "Toast", "doordash": "DoorDash", "ubereats": "UberEats", "shopify": "Shopify",
                  "stripe": "Stripe", "lawpay": "LawPay"}
GROSS_KEYWORDS = ("gross", "subtotal", "sales", "order total", "amount", "total")
NET_KEYWORDS = ("net", "payout", "deposit")
FEE_KEYWORDS = ("fee", "commission", "charge")
FILE_FEE_PLATFORMS = {"lawpay"}
QBO_HEADERS = ["Journal No", "Journal Date", "Account", "Debits", "Credits", "Description", "Name", "Memo"]

SAMPLE_CSV = {
    "toast": "Business Date,Order Count,Gross Sales,Discounts,Net Sales,Deposit Amount\n"
             "2026-09-01,84,2841.50,40.00,2801.50,1961.05\n2026-09-02,91,3120.75,0.00,3120.75,2184.53\n"
             "2026-09-03,77,2560.20,25.50,2534.70,1774.29\n",
    "doordash": "Payout Date,Order ID,Subtotal,Commission,Net Total\n"
                "2026-09-04,DD-10021,64.20,19.26,44.94\n2026-09-04,DD-10022,38.90,11.67,27.23\n"
                "2026-09-05,DD-10023,112.45,33.74,78.71\n2026-09-05,DD-10024,57.10,17.13,39.97\n",
    "ubereats": "Date,Order ID,Sales (incl. tax),Uber Service Fee,Total Payout\n"
                "2026-09-06,UE-5501,48.75,14.63,34.12\n2026-09-06,UE-5502,92.30,27.69,64.61\n"
                "2026-09-07,UE-5503,31.15,9.35,21.80\n",
    "shopify": "Payout Date,Transaction ID,Gross Amount,Fee,Net Payout\n"
               "2026-09-08,SH-7781,149.00,4.62,144.38\n2026-09-08,SH-7782,89.50,2.90,86.60\n"
               "2026-09-09,SH-7783,320.00,9.58,310.42\n",
    "stripe": "id,Created (UTC),Gross,Fee,Net\n"
              "txn_1,2026-09-10,250.00,7.55,242.45\ntxn_2,2026-09-10,99.00,3.17,95.83\n"
              "txn_3,2026-09-11,1200.00,35.10,1164.90\n",
    "lawpay": "Date,Transaction ID,Client Matter,Deposit Account,Amount,Fee,Net Deposit\n"
              "2026-09-12,LP-90311,Harper v. Lane - Retainer,Trust,5000.00,147.50,5000.00\n"
              "2026-09-12,LP-90312,Estate of Moreno - Retainer,Trust,2500.00,73.75,2500.00\n"
              "2026-09-13,LP-90313,Kim LLC - Retainer,Trust,1750.00,51.63,1750.00\n",
}


def _to_number(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.replace(r"[\$,\s]", "", regex=True)
    negative = s.str.startswith("(") & s.str.endswith(")")
    s = s.str.strip("()")
    nums = pd.to_numeric(s, errors="coerce")
    return nums.where(~negative, -nums)


def _pick_column(df: pd.DataFrame, keywords, exclude=()):
    for kw in keywords:
        for col in df.columns:
            name = str(col).strip().lower()
            if kw in name and not any(x in name for x in exclude) and _to_number(df[col]).notna().any():
                return col
    return None


def _sum(series: pd.Series) -> Decimal:
    return sum((d2(v) for v in _to_number(series).dropna()), Decimal("0"))


def effective_rate(gross_total: float, fee_total: float) -> float:
    return float(d2(Decimal(str(fee_total)) / Decimal(str(gross_total)) * 100)) if gross_total else 0.0


def parse_platform_csv(raw: bytes, platform: str = "") -> dict:
    """Detects gross/net/fee columns; LawPay requires an explicit fee column (exact fees, no percentage)."""
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding_errors="replace")
    except Exception:
        raise ValueError("Could not read this file as CSV")
    if df.empty:
        raise ValueError("The CSV file has no data rows")
    gross_col = _pick_column(df, GROSS_KEYWORDS, exclude=("net", "fee", "commission", "count", "id", "payout"))
    if gross_col is None:
        raise ValueError(f"Could not detect a gross sales column. Columns found: {', '.join(map(str, df.columns))}")
    net_col = _pick_column(df, NET_KEYWORDS, exclude=("fee", "commission", "date", "id", "count", "net sales"))
    fee_col = _pick_column(df, FEE_KEYWORDS, exclude=("net", "gross", "rate", "%", "date", "id", "type"))
    if platform in FILE_FEE_PLATFORMS and fee_col is None:
        raise ValueError(f"Could not find a fee column in this file. Columns found: {', '.join(map(str, df.columns))}")
    fees = _to_number(df[fee_col]).dropna() if fee_col is not None else pd.Series(dtype=float)
    return {
        "rows_parsed": int(len(df)),
        "gross_column": str(gross_col),
        "net_column": str(net_col) if net_col is not None else None,
        "gross_total": float(_sum(df[gross_col])),
        "file_net_total": float(_sum(df[net_col])) if net_col is not None else None,
        "fee_column": str(fee_col) if fee_col is not None else None,
        "fee_total": float(sum((abs(d2(v)) for v in fees), Decimal("0"))) if fee_col is not None else None,
        "fee_line_items": int(len(fees)),
    }


def _trust_ledger(gross: Decimal, fees: Decimal) -> dict:
    """LawPay trust deposits: full amount stays in trust, exact processing fees post against operating."""
    lines = [
        {"account": "Trust Bank Account (IOLTA)", "side": "debit", "debit": float(gross), "credit": 0.0,
         "memo": "Full client funds deposited to trust"},
        {"account": "Client Trust Liability", "side": "credit", "debit": 0.0, "credit": float(gross),
         "memo": "Funds held in trust for clients"},
        {"account": "Credit Card Processing Fees", "side": "debit", "debit": float(fees), "credit": 0.0,
         "memo": "LawPay processing fees (line items from file)"},
        {"account": "Operating Bank Account", "side": "credit", "debit": 0.0, "credit": float(fees),
         "memo": "Fees paid from operating, not trust"},
    ]
    total = gross + fees
    return {"lines": lines, "total_debits": float(total), "total_credits": float(total),
            "difference": 0.0, "balanced": True}


def build_ledger(gross_total: float, commission_rate: float, platform: str = "", fee_total: float = None) -> dict:
    gross = d2(gross_total)
    if platform in FILE_FEE_PLATFORMS:
        return _trust_ledger(gross, d2(fee_total))
    rate = Decimal(str(commission_rate)) / Decimal("100")
    commission = d2(gross * rate)
    net = gross - commission
    lines = [
        {"account": "Bank Clearing Account", "side": "debit", "debit": float(net), "credit": 0.0,
         "memo": "Net cash deposited"},
        {"account": "Delivery Commissions Expense", "side": "debit", "debit": float(commission), "credit": 0.0,
         "memo": f"Platform commission @ {commission_rate:g}%"},
        {"account": "Gross Sales Revenue", "side": "credit", "debit": 0.0, "credit": float(gross),
         "memo": "Total gross sales"},
    ]
    total_debits = net + commission
    return {
        "lines": lines,
        "total_debits": float(total_debits),
        "total_credits": float(gross),
        "difference": float(total_debits - gross),
        "balanced": total_debits == gross,
    }


def net_variance(file_net_total, ledger: dict):
    """Compares the file's reported net payout with the cash deposit line of the journal entry."""
    if file_net_total is None:
        return None
    file_net, calculated = d2(file_net_total), d2(ledger["lines"][0]["debit"])
    diff = file_net - calculated
    return {"file_net": float(file_net), "calculated_net": float(calculated),
            "difference": float(diff), "flagged": diff != 0}


def ledger_to_qbo_csv(payout: dict) -> bytes:
    journal_no = f"LS-{payout['id'][-6:].upper()}"
    journal_date = date.today().strftime("%m/%d/%Y")
    desc = safe_cell(f"{PLATFORM_NAMES.get(payout['platform'], payout['platform'])} payout split - {payout['filename']}")
    rows = [
        [journal_no, journal_date, line["account"],
         f"{line['debit']:.2f}" if line["debit"] else "",
         f"{line['credit']:.2f}" if line["credit"] else "",
         desc, safe_cell(payout.get("client_name", "")), safe_cell(line["memo"])]
        for line in payout["ledger"]["lines"]
    ]
    return pd.DataFrame(rows, columns=QBO_HEADERS).to_csv(index=False).encode("utf-8")


# =====================================================================
# Emergent managed email (Resend) with safety gate
# =====================================================================
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                   headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning("Email paused: %s (%s): %s", code, e.response.status_code, e.response.text)
            raise HTTPException(status_code=503, detail="Email is temporarily unavailable")
        logger.error("Email send failed: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(status_code=502, detail="Failed to send email")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email send error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to send email")


# =====================================================================
# Request models
# =====================================================================
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    firm_name: str = Field(default="", max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    industry: str = Field(default="", max_length=80)
    contact_email: str = Field(default="", max_length=160)
    platforms: List[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1000)


class RateIn(BaseModel):
    commission_rate: float = Field(ge=0, le=100)


class StatementRow(BaseModel):
    id: str
    date: str
    description: str = ""
    reference: str = ""
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    balance: Optional[float] = None


class StatementRows(BaseModel):
    rows: List[StatementRow]


class CheckoutIn(BaseModel):
    plan: str
    origin_url: str


class PortalIn(BaseModel):
    origin_url: str


class ContactIn(BaseModel):
    desk: Literal["support", "sales"]
    name: str = Field(min_length=1, max_length=120)
    role: Literal["firm_owner", "staff_bookkeeper", "freelance_bookkeeper", "controller", "other"]
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "message", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


# =====================================================================
# FastAPI application
# =====================================================================
app = FastAPI(title="LedgerStream AI")


@app.get("/api/")
async def root():
    return {"service": "LedgerStream AI", "status": "ok"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "textract_configured": textract_enabled()}


# ---------- Auth ----------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def new_user_doc(email: str, name: str, provider: str, **extra) -> dict:
    return {
        "user_id": new_id("user"), "email": email, "name": name, "auth_provider": provider,
        "plan": "free", "subscription_status": "trial", "pages_used": 0, "created_at": now(), **extra,
    }


@app.post("/api/auth/register")
async def register(body: RegisterIn, request: Request, response: Response):
    await throttle(request, "register", 20)
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    doc = new_user_doc(email, body.name.strip(), "password",
                       firm_name=body.firm_name.strip(), password_hash=hash_password(body.password))
    await db.users.insert_one(doc)
    refresh_token = set_auth_cookies(response, doc["user_id"], email)
    return {**public_user(doc), "csrf_token": csrf_token_for(refresh_token)}


@app.post("/api/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower()
    identifier = f"{client_ip(request)}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("locked_until") and _as_utc(attempt["locked_until"]) > now():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        count = (attempt or {}).get("count", 0) + 1
        update = {"count": count, "updated_at": now()}
        if count >= MAX_LOGIN_ATTEMPTS:
            update = {"count": 0, "locked_until": now() + timedelta(minutes=LOCKOUT_MINUTES)}
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    refresh_token = set_auth_cookies(response, user["user_id"], email)
    return {**public_user(user), "csrf_token": csrf_token_for(refresh_token)}


@app.post("/api/auth/google/session")
async def google_session(body: GoogleSessionIn, response: Response):
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Google sign-in failed")
    data = r.json()
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": data.get("picture")}})
        user["picture"] = data.get("picture")
    else:
        user = new_user_doc(email, data.get("name", ""), "google", picture=data.get("picture"))
        await db.users.insert_one(user)
        user.pop("_id", None)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": data["session_token"],
        "expires_at": now() + timedelta(days=7), "created_at": now(),
    })
    response.set_cookie("session_token", data["session_token"], max_age=604800, **COOKIE_OPTS)
    return {**public_user(user), "csrf_token": csrf_token_for(data["session_token"])}


@app.get("/api/auth/me")
async def me(request: Request, user: dict = Depends(get_current_user)):
    return {**public_user(user), "csrf_token": request_csrf_token(request)}


@app.post("/api/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"]), max_age=900, **COOKIE_OPTS)
    return {"ok": True}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    session = request.cookies.get("session_token")
    if session:
        await db.user_sessions.delete_one({"session_token": session})
    for name in ("access_token", "refresh_token", "session_token"):
        response.delete_cookie(name, path="/", secure=True, samesite="none")
    return {"ok": True}


@app.post("/api/auth/forgot-password")
async def forgot_password(body: ForgotIn, request: Request):
    await throttle(request, "forgot", 5)
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": user["user_id"], "used": False,
            "expires_at": now() + timedelta(hours=1),
        })
        try:
            base = trusted_origin(request.headers.get("origin", ""), request)
        except HTTPException:
            base = ALLOWED_ORIGINS[0]
        try:
            await send_email(to=user["email"], subject=f"Reset your {EMAIL_FROM_NAME} password",
                             html=_render_reset_email(user.get("name", ""), f"{base}/reset-password?token={token}"))
        except HTTPException as e:
            logger.warning("Password reset email failed for %s: %s", user["user_id"], e.detail)
    return {"ok": True}


def _render_reset_email(name: str, link: str) -> str:
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;background:#f8fafc">'
        '<tr><td style="padding:24px">'
        '<h2 style="margin:0 0 12px;font-size:18px;color:#0b132b">Reset your password</h2>'
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.5;color:#0f172a">Hi {escape(name or "there")}, we received a '
        f'request to reset the password for your {escape(EMAIL_FROM_NAME)} account. The link below expires in 1 hour.</p>'
        f'<p style="margin:20px 0"><a href="{escape(link)}" style="background:#10b981;color:#052e1f;padding:10px 18px;'
        'border-radius:6px;text-decoration:none;font-weight:bold">Choose a new password</a></p>'
        '<p style="margin:0 0 12px;font-size:13px;color:#64748b">If you did not ask for this, you can ignore this email and '
        'your password stays the same.</p>'
        f'<p style="margin-top:16px;font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. '
        'We never ask for your password or card details by email.</p>'
        '</td></tr></table>'
    )


@app.post("/api/auth/reset-password")
async def reset_password(body: ResetIn):
    rec = await db.password_reset_tokens.find_one({"token": body.token, "used": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or used reset token")
    if _as_utc(rec["expires_at"]) < now():
        raise HTTPException(status_code=400, detail="Reset token expired")
    await db.users.update_one({"user_id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}


# ---------- Clients ----------
def _clean_client(body: ClientIn) -> dict:
    data = body.model_dump()
    data["name"] = data["name"].strip()
    data["platforms"] = [p for p in data["platforms"] if p in PLATFORMS]
    return data


@app.get("/api/clients")
async def list_clients(user: dict = Depends(get_current_user)):
    owner = user["user_id"]
    clients = await db.clients.find({"owner_id": owner}, {"_id": 0}).sort("created_at", -1).to_list(500)
    stats = {}
    async for s in db.statements.aggregate([
        {"$match": {"owner_id": owner}},
        {"$group": {"_id": "$client_id", "statements": {"$sum": 1}, "pages": {"$sum": "$pages"}}},
    ]):
        stats[s["_id"]] = {"statements": s["statements"], "pages": s["pages"]}
    payout_counts = {}
    async for p in db.payouts.aggregate([
        {"$match": {"owner_id": owner}}, {"$group": {"_id": "$client_id", "n": {"$sum": 1}}},
    ]):
        payout_counts[p["_id"]] = p["n"]
    for c in clients:
        st = stats.get(c["id"], {})
        c["statements_count"] = st.get("statements", 0)
        c["pages_converted"] = st.get("pages", 0)
        c["payouts_count"] = payout_counts.get(c["id"], 0)
    return clients


@app.post("/api/clients")
async def create_client(body: ClientIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id("cli"), "owner_id": user["user_id"], **_clean_client(body), "created_at": now().isoformat()}
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc


@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, body: ClientIn, user: dict = Depends(get_current_user)):
    owner = user["user_id"]
    await get_owned_client(owner, client_id)
    data = _clean_client(body)
    await db.clients.update_one({"id": client_id, "owner_id": owner}, {"$set": data})
    await db.statements.update_many({"client_id": client_id, "owner_id": owner}, {"$set": {"client_name": data["name"]}})
    await db.payouts.update_many({"client_id": client_id, "owner_id": owner}, {"$set": {"client_name": data["name"]}})
    return await get_owned_client(owner, client_id)


@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, user: dict = Depends(get_current_user)):
    await get_owned_client(user["user_id"], client_id)
    await db.clients.delete_one({"id": client_id, "owner_id": user["user_id"]})
    return {"ok": True}


# ---------- Bank Statement Converter ----------
async def _read_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit")
    return raw


async def _last_textract_check(user_id: str):
    return await db.textract_checks.find_one({"user_id": user_id}, {"_id": 0, "user_id": 0}, sort=[("checked_at", -1)])


@app.get("/api/statements/engine")
async def statement_engine(user: dict = Depends(get_current_user)):
    return {"engine": "aws_textract", "configured": textract_enabled(), "region": os.environ.get("AWS_REGION", ""),
            "last_check": await _last_textract_check(user["user_id"])}


@app.post("/api/statements/engine/check")
async def check_textract(user: dict = Depends(get_current_user)):
    last = await _last_textract_check(user["user_id"])
    if last and _as_utc(last["checked_at"]) > now() - timedelta(seconds=DIAG_COOLDOWN_SECONDS):
        raise HTTPException(status_code=429, detail=f"Please wait {DIAG_COOLDOWN_SECONDS} seconds between connection checks")
    result = await run_in_threadpool(run_textract_diagnostic)
    doc = {"user_id": user["user_id"], **result, "checked_at": now().isoformat()}
    await db.textract_checks.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("user_id", None)
    return doc


@app.post("/api/statements")
async def convert_statement(
    file: UploadFile = File(...), client_id: str = Form(...), user: dict = Depends(get_current_user),
):
    client_doc = await get_owned_client(user["user_id"], client_id)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF bank statements are supported")
    if not textract_enabled():
        raise HTTPException(
            status_code=503,
            detail="Amazon Textract is not connected yet. Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_REGION to enable PDF parsing.",
        )
    raw = await _read_upload(file)
    try:
        pages = await run_in_threadpool(count_pages, raw)
    except Exception:
        raise HTTPException(status_code=400, detail="This file is not a readable PDF")
    if not await reserve_pages(user, pages):
        raise HTTPException(status_code=402, detail=page_limit_message(user, pages))
    try:
        rows = await run_in_threadpool(run_statement_pipeline, raw)
    except Exception as e:
        await release_pages(user, pages)
        logger.exception("Textract pipeline failed")
        reason = str(e) if isinstance(e, (TextractError, TextractNotConfigured)) else "Statement parsing failed"
        raise HTTPException(status_code=424, detail=f"{reason}. Your pages were not charged.")
    doc = {
        "id": new_id("stm"), "kind": "statement", "owner_id": user["user_id"],
        "client_id": client_doc["id"], "client_name": client_doc["name"], "filename": file.filename,
        "pages": pages, "engine": "aws_textract", "status": "completed", "rows": rows,
        "summary": summarize(rows), "created_at": now().isoformat(),
    }
    await db.statements.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _owned_statement(user: dict, statement_id: str) -> dict:
    doc = await db.statements.find_one({"id": statement_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Statement not found")
    return doc


@app.get("/api/statements/{statement_id}")
async def get_statement(statement_id: str, user: dict = Depends(get_current_user)):
    return await _owned_statement(user, statement_id)


@app.put("/api/statements/{statement_id}/rows")
async def save_rows(statement_id: str, body: StatementRows, user: dict = Depends(get_current_user)):
    await _owned_statement(user, statement_id)
    rows = normalize_rows([r.model_dump() for r in body.rows])
    await db.statements.update_one(
        {"id": statement_id, "owner_id": user["user_id"]},
        {"$set": {"rows": rows, "summary": summarize(rows), "updated_at": now().isoformat()}},
    )
    return await _owned_statement(user, statement_id)


@app.get("/api/statements/{statement_id}/export")
async def export_statement(statement_id: str, fmt: str = "csv", user: dict = Depends(get_current_user)):
    doc = await _owned_statement(user, statement_id)
    fmt = "xlsx" if fmt == "xlsx" else "csv"
    content = await run_in_threadpool(rows_to_export, doc["rows"], fmt)
    base = doc["filename"].rsplit(".", 1)[0]
    media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{base}_ledger.{fmt}"'})


@app.post("/api/webhooks/textract")
async def textract_webhook(request: Request):
    """Async Textract connector: body {statement_id, Blocks:[...]}, HMAC-SHA256 signed."""
    body = await request.body()
    expected = hmac.new(os.environ["TEXTRACT_WEBHOOK_SECRET"].encode(), body, hashlib.sha256).hexdigest()
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
    rows = dataframe_to_rows(blocks_to_dataframe(blocks))
    await db.statements.update_one({"id": statement_id}, {"$set": {
        "rows": rows, "summary": summarize(rows), "engine": "aws_textract",
        "status": "completed", "updated_at": now().isoformat(),
    }})
    return {"ok": True, "transactions": len(rows)}


# ---------- Merchant Payout Splitter ----------
@app.get("/api/payouts/sample/{platform}")
async def sample_payout_csv(platform: str, user: dict = Depends(get_current_user)):
    if platform not in SAMPLE_CSV:
        raise HTTPException(status_code=404, detail="Unknown platform")
    return Response(SAMPLE_CSV[platform], media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sample_{platform}_payout.csv"'})


@app.post("/api/payouts")
async def split_payout(
    file: UploadFile = File(...), client_id: str = Form(...), platform: str = Form(...),
    commission_rate: float = Form(30.0), user: dict = Depends(get_current_user),
):
    client_doc = await get_owned_client(user["user_id"], client_id)
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    if not 0 <= commission_rate <= 100:
        raise HTTPException(status_code=400, detail="Commission rate must be between 0 and 100")
    raw = await _read_upload(file)
    try:
        parsed = await run_in_threadpool(parse_platform_csv, raw, platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if platform in FILE_FEE_PLATFORMS:
        commission_rate = effective_rate(parsed["gross_total"], parsed["fee_total"])
    ledger = build_ledger(parsed["gross_total"], commission_rate, platform, parsed["fee_total"])
    doc = {
        "id": new_id("pay"), "kind": "payout", "owner_id": user["user_id"],
        "client_id": client_doc["id"], "client_name": client_doc["name"], "platform": platform,
        "filename": file.filename, **parsed, "commission_rate": commission_rate,
        "ledger": ledger, "net_variance": net_variance(parsed["file_net_total"], ledger),
        "created_at": now().isoformat(),
    }
    await db.payouts.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _owned_payout(user: dict, payout_id: str) -> dict:
    doc = await db.payouts.find_one({"id": payout_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payout not found")
    return doc


@app.get("/api/payouts/{payout_id}")
async def get_payout(payout_id: str, user: dict = Depends(get_current_user)):
    return await _owned_payout(user, payout_id)


@app.post("/api/payouts/{payout_id}/recalculate")
async def recalculate_payout(payout_id: str, body: RateIn, user: dict = Depends(get_current_user)):
    doc = await _owned_payout(user, payout_id)
    if doc["platform"] in FILE_FEE_PLATFORMS:
        raise HTTPException(status_code=400, detail="LawPay fees are read from the file and can't be recalculated with a rate")
    ledger = build_ledger(doc["gross_total"], body.commission_rate, doc["platform"])
    update = {"commission_rate": body.commission_rate, "ledger": ledger,
              "net_variance": net_variance(doc.get("file_net_total"), ledger)}
    await db.payouts.update_one({"id": payout_id, "owner_id": user["user_id"]}, {"$set": update})
    return {**doc, **update}


@app.get("/api/payouts/{payout_id}/qbo")
async def payout_qbo_csv(payout_id: str, user: dict = Depends(get_current_user)):
    doc = await _owned_payout(user, payout_id)
    return Response(ledger_to_qbo_csv(doc), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="qbo_journal_{doc["platform"]}_{payout_id[-6:]}.csv"'})


# ---------- History & Dashboard ----------
LIST_PROJECTION = {"_id": 0, "rows": 0}


@app.get("/api/history")
async def history(client_id: Optional[str] = None, kind: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {"owner_id": user["user_id"]}
    if client_id:
        query["client_id"] = client_id
    if kind == "needs_review":
        return await db.statements.find(
            {**query, "summary.reconciliation.status": "mismatch"}, LIST_PROJECTION
        ).sort("created_at", -1).to_list(1000)
    if kind == "variance":
        return await db.payouts.find(
            {**query, "net_variance.flagged": True}, LIST_PROJECTION
        ).sort("created_at", -1).to_list(1000)
    items = []
    if kind in (None, "statement"):
        items += await db.statements.find(query, LIST_PROJECTION).to_list(1000)
    if kind in (None, "payout"):
        items += await db.payouts.find(query, LIST_PROJECTION).to_list(1000)
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


@app.get("/api/history/review-count")
async def review_count(user: dict = Depends(get_current_user)):
    owner = user["user_id"]
    return {
        "needs_review": await db.statements.count_documents({"owner_id": owner, "summary.reconciliation.status": "mismatch"}),
        "variance": await db.payouts.count_documents({"owner_id": owner, "net_variance.flagged": True}),
    }


VARIANCE_HEADERS = ["Date", "Client", "Platform", "File", "Gross Sales", "Commission / Fee Basis",
                    "File Net Payout", "Journal Deposit", "Difference"]


def variance_to_csv(payouts: list) -> bytes:
    rows = [[
        p["created_at"][:10], safe_cell(p.get("client_name", "")), PLATFORM_NAMES.get(p["platform"], p["platform"]),
        safe_cell(p["filename"]),
        f"{p['gross_total']:.2f}",
        f"{p['fee_total']:.2f} fees from file" if p["platform"] in FILE_FEE_PLATFORMS else f"{p['commission_rate']:g}% commission",
        f"{p['net_variance']['file_net']:.2f}", f"{p['net_variance']['calculated_net']:.2f}",
        f"{p['net_variance']['difference']:.2f}",
    ] for p in payouts]
    if rows:
        total = sum((d2(p["net_variance"]["difference"]) for p in payouts), Decimal("0"))
        rows.append(["Total", "", "", f"{len(payouts)} flagged payout(s)", "", "", "", "", f"{total:.2f}"])
    return pd.DataFrame(rows, columns=VARIANCE_HEADERS).to_csv(index=False).encode("utf-8")


@app.get("/api/history/variance-export")
async def variance_export(client_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {"owner_id": user["user_id"], "net_variance.flagged": True}
    label = "all_clients"
    if client_id:
        client_doc = await get_owned_client(user["user_id"], client_id)
        query["client_id"] = client_id
        label = re.sub(r"[^a-z0-9]+", "_", client_doc["name"].lower()).strip("_") or "client"
    payouts = await db.payouts.find(query, LIST_PROJECTION).sort("created_at", 1).to_list(5000)
    return Response(variance_to_csv(payouts), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="payout_variances_{label}.csv"'})


@app.delete("/api/history/{kind}/{item_id}")
async def delete_history(kind: str, item_id: str, user: dict = Depends(get_current_user)):
    coll = {"statement": db.statements, "payout": db.payouts}.get(kind)
    if coll is None:
        raise HTTPException(status_code=404, detail="Not found")
    res = await coll.delete_one({"id": item_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@app.get("/api/dashboard/summary")
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


# ---------- Billing (Stripe subscriptions) ----------
async def _activate(session_id: str, session=None):
    """Idempotently marks a transaction paid and upgrades the user's plan."""
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "stripe_subscription_id": getattr(session, "subscription", None) if session else None,
                  "stripe_customer_id": getattr(session, "customer", None) if session else None,
                  "updated_at": now()}},
    )
    if res.modified_count == 0:
        return
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    await db.users.update_one({"user_id": tx["user_id"]}, {"$set": {
        "plan": tx["plan"], "subscription_status": "active_subscriber", "stripe_customer_id": tx.get("stripe_customer_id"),
        "stripe_subscription_id": tx.get("stripe_subscription_id"), "plan_updated_at": now(),
    }})


def _create_checkout_session(kwargs):
    if STRIPE_TAX_MODE == "full":
        try:
            return stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or str(e)).lower()
            if "managed payments" not in msg and "ineligible" not in msg and "managed_payments" not in msg:
                raise
            logger.warning("Managed payments unavailable, falling back to automatic tax: %s", msg)
    return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")


@app.get("/api/billing/summary")
async def billing_summary(user: dict = Depends(get_current_user)):
    return {**public_user(user), "has_portal": bool(user.get("stripe_customer_id"))}


@app.post("/api/payments/checkout")
async def create_checkout(body: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    lookup_key = PLAN_LOOKUP.get(body.plan)
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Unknown plan")
    prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(status_code=500, detail=f"Price not found: {lookup_key}")
    price = prices[0]
    origin = trusted_origin(body.origin_url, request)
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        customer_email=user["email"],
        metadata={"user_id": user["user_id"], "plan": body.plan, "lookup_key": lookup_key},
    )
    try:
        session = _create_checkout_session(kwargs)
    except stripe.error.StripeError as e:
        logger.exception("Stripe checkout failed")
        raise HTTPException(status_code=502, detail=e.user_message or "Payment provider error")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["user_id"], "plan": body.plan, "lookup_key": lookup_key,
        "amount": float(price.unit_amount or 0) / 100.0, "currency": price.currency,
        "status": "initiated", "payment_status": "pending", "created_at": now(), "updated_at": now(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


@app.get("/api/payments/status/{session_id}")
async def payment_status(session_id: str, user: dict = Depends(get_current_user)):
    record = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await _activate(session_id, s)
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"], "plan": record.get("plan")}


def _portal_configuration_id() -> str:
    """Portal config that lets subscribers switch between Starter and Agency."""
    products = []
    for lookup_key in PLAN_LOOKUP.values():
        price = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data[0]
        products.append({"product": price.product, "prices": [price.id]})
    features = {
        "invoice_history": {"enabled": True},
        "payment_method_update": {"enabled": True},
        "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
        "subscription_update": {"enabled": True, "default_allowed_updates": ["price"],
                                "proration_behavior": "create_prorations", "products": products},
    }
    for cfg in stripe.billing_portal.Configuration.list(active=True, limit=20).auto_paging_iter():
        if cfg.metadata.get("managed_by") == "ledgerstream":
            return stripe.billing_portal.Configuration.modify(cfg.id, features=features).id
    return stripe.billing_portal.Configuration.create(
        business_profile={"headline": "LedgerStream AI billing"}, features=features,
        metadata={"managed_by": "ledgerstream"},
    ).id


@app.post("/api/billing/portal")
async def billing_portal(body: PortalIn, request: Request, user: dict = Depends(get_current_user)):
    customer = user.get("stripe_customer_id")
    if not customer or user.get("plan") not in PAID_PLANS:
        raise HTTPException(status_code=400, detail="No active subscription to manage yet")
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer, configuration=_portal_configuration_id(),
            return_url=f"{trusted_origin(body.origin_url, request)}/billing",
        )
    except stripe.error.StripeError as e:
        logger.exception("Stripe portal failed")
        raise HTTPException(status_code=502, detail=e.user_message or "Could not open the billing portal")
    return {"url": session.url}


@app.post("/api/webhooks/stripe")
@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), STRIPE_WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if obj.get("payment_status") == "paid" or obj.get("status") == "complete":
            await _activate(obj["id"], stripe.checkout.Session.construct_from(obj, stripe.api_key))
    elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        status = "failed" if t.endswith("failed") else "expired"
        await db.payment_transactions.update_one({"session_id": obj["id"]},
                                                 {"$set": {"status": status, "payment_status": status, "updated_at": now()}})
    elif t == "customer.subscription.updated" and obj.get("status") in ("active", "trialing"):
        items = (obj.get("items") or {}).get("data") or []
        lookup_key = items[0]["price"].get("lookup_key") if items else None
        plan = next((p for p, k in PLAN_LOOKUP.items() if k == lookup_key), None)
        if plan:
            await db.users.update_one(
                {"$or": [{"stripe_subscription_id": obj["id"]}, {"stripe_customer_id": obj.get("customer") or "_none_"}]},
                {"$set": {"plan": plan, "subscription_status": "active_subscriber",
                          "stripe_subscription_id": obj["id"], "plan_updated_at": now()}},
            )
    elif t == "customer.subscription.deleted":
        match = [{"stripe_subscription_id": obj["id"]}]
        if obj.get("customer"):
            match.append({"stripe_customer_id": obj["customer"]})
        await db.users.update_one(
            {"$or": match},
            {"$set": {"plan": "free", "subscription_status": "trial", "plan_updated_at": now()}},
        )
    logger.info("Stripe webhook processed: %s", t)
    return {"status": "ok"}


# ---------- Contact form (routes to support/sales desk + confirmation email) ----------
CONTACT_DESKS = {
    "support": ("General Support & Engineering", "SUPPORT_DESK_EMAIL"),
    "sales": ("Enterprise & Firm Sales", "SALES_DESK_EMAIL"),
}
CONTACT_ROLES = {
    "firm_owner": "Firm owner / CPA",
    "staff_bookkeeper": "Staff bookkeeper",
    "freelance_bookkeeper": "Freelance bookkeeper",
    "controller": "Controller / finance lead",
    "other": "Other",
}
CONTACT_HOURLY_LIMIT = 5
CONTACT_RESPONSE_TIMES = {
    "support": "an engineer will review and follow up within 12 business hours",
    "sales": "our partnership team will send pricing or a processing quote within 1 business day",
}


def _render_contact_confirmation(name: str, desk_label: str, desk: str, ref: str) -> str:
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;background:#f8fafc">'
        '<tr><td style="padding:24px">'
        '<h2 style="margin:0 0 12px;font-size:18px;color:#0b132b">We got your message</h2>'
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.5;color:#0f172a">Hi {escape(name)}, thanks for contacting '
        f'the {escape(EMAIL_FROM_NAME)} {escape(desk_label)} desk. Your message has been received and '
        f'{escape(CONTACT_RESPONSE_TIMES[desk])}.</p>'
        f'<p style="margin:0 0 12px;font-size:13px;color:#64748b">Reference: {escape(ref)}</p>'
        f'<p style="margin-top:16px;font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. '
        'We never ask for your password or card details by email.</p>'
        '</td></tr></table>'
    )


def _render_contact_message(desk_label: str, name: str, email: str, role: str, firm: str, plan: str, message: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#64748b;font-size:13px">{k}</td>'
        f'<td style="padding:4px 0;font-size:13px;color:#0f172a">{v}</td></tr>'
        for k, v in [("Name", escape(name)), ("Account email", escape(email)), ("Role", escape(role)),
                     ("Firm", escape(firm or "-")), ("Plan", escape(plan))]
    )
    body = escape(message).replace("\n", "<br>")
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;background:#f8fafc">'
        '<tr><td style="padding:24px">'
        f'<h2 style="margin:0 0 4px;font-size:18px;color:#0b132b">New {escape(desk_label)} message</h2>'
        '<p style="margin:0 0 16px;font-size:13px;color:#64748b">Submitted through the in-app contact form.</p>'
        f'<table role="presentation">{rows}</table>'
        '<div style="margin-top:16px;padding:16px;background:#ffffff;border:1px solid #e2e8f0;'
        f'border-radius:8px;font-size:14px;line-height:1.5;color:#0f172a">{body}</div>'
        f'<p style="margin-top:16px;font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. '
        'Reply to the account email above to respond.</p>'
        '</td></tr></table>'
    )


@app.post("/api/contact")
async def submit_contact(body: ContactIn, user: dict = Depends(get_current_user)):
    since = (now() - timedelta(hours=1)).isoformat()
    recent = await db.contact_messages.count_documents(
        {"user_id": user["user_id"], "created_at": {"$gte": since}, "status": {"$ne": "failed"}})
    if recent >= CONTACT_HOURLY_LIMIT:
        raise HTTPException(status_code=429, detail="You've sent several messages recently. Please try again in an hour.")
    desk_label, env_key = CONTACT_DESKS[body.desk]
    record = {
        "id": new_id("msg"), "user_id": user["user_id"], "email": user["email"], "desk": body.desk,
        "name": body.name, "role": body.role, "message": body.message,
        "status": "pending", "created_at": now().isoformat(),
    }
    await db.contact_messages.insert_one(record)
    html = _render_contact_message(desk_label, record["name"], user["email"], CONTACT_ROLES[body.role],
                                   user.get("firm_name", ""), user.get("plan", "free"), record["message"])
    try:
        email_id = await send_email(to=os.environ[env_key],
                                    subject=f"[{EMAIL_FROM_NAME}] {desk_label} message from {body.name}", html=html)
    except HTTPException:
        await db.contact_messages.update_one({"id": record["id"]}, {"$set": {"status": "failed"}})
        raise
    await db.contact_messages.update_one({"id": record["id"]}, {"$set": {"status": "sent", "email_id": email_id}})
    confirmation = "sent"
    try:
        await send_email(
            to=user["email"], subject=f"We got your message - {EMAIL_FROM_NAME}",
            html=_render_contact_confirmation(record["name"], desk_label, body.desk, record["id"]),
        )
    except HTTPException as e:
        confirmation = "failed"
        logger.warning("Confirmation email failed for %s: %s", record["id"], e.detail)
    await db.contact_messages.update_one({"id": record["id"]}, {"$set": {"confirmation_status": confirmation}})
    return {"ok": True, "id": record["id"], "desk": body.desk, "confirmation_sent": confirmation == "sent"}


# ---------- Startup: indexes + optional demo account ----------
DEMO_CLIENTS = [
    {"name": "The Burger Shack", "industry": "Restaurant", "platforms": ["toast", "doordash", "ubereats"]},
    {"name": "Downtown Boutique", "industry": "Retail / E-commerce", "platforms": ["shopify", "stripe"]},
]


async def seed_demo_user():
    email, password = os.environ["DEMO_EMAIL"].lower(), os.environ["DEMO_PASSWORD"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing is None:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": "Demo Bookkeeper", "firm_name": "Demo Bookkeeping Co.",
            "auth_provider": "password", "password_hash": hash_password(password),
            "plan": "free", "subscription_status": "trial", "pages_used": 0, "created_at": now(),
        })
        for c in DEMO_CLIENTS:
            await db.clients.insert_one({
                "id": new_id("cli"), "owner_id": user_id, "contact_email": "", "notes": "",
                **c, "created_at": now().isoformat(),
            })
    elif not existing.get("password_hash") or not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


_initialized = False


async def ensure_initialized():
    """Runs index creation and demo seeding once per process / warm Lambda container."""
    global _initialized
    if _initialized:
        return
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.login_attempts.create_index("identifier")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.clients.create_index([("owner_id", 1), ("created_at", -1)])
    await db.statements.create_index([("owner_id", 1), ("created_at", -1)])
    await db.payouts.create_index([("owner_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.contact_messages.create_index([("user_id", 1), ("created_at", -1)])
    await db.textract_checks.create_index([("user_id", 1), ("checked_at", -1)])
    await db.rate_limits.create_index("created_at", expireAfterSeconds=3600)
    async for p in db.payouts.find({"net_variance": {"$exists": False}, "ledger.lines.0": {"$exists": True}},
                                   {"_id": 0, "id": 1, "file_net_total": 1, "ledger": 1}):
        await db.payouts.update_one({"id": p["id"]}, {"$set": {"net_variance": net_variance(p.get("file_net_total"), p["ledger"])}})
    if os.environ.get("DEMO_EMAIL") and os.environ.get("DEMO_PASSWORD"):
        await seed_demo_user()
    _initialized = True


@app.middleware("http")
async def init_once(request: Request, call_next):
    await ensure_initialized()
    return await call_next(request)


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    unsafe = request.method in ("POST", "PUT", "PATCH", "DELETE")
    has_session = any(request.cookies.get(n) for n in (*CSRF_COOKIES, "access_token"))
    if unsafe and has_session and not request.url.path.startswith(CSRF_EXEMPT) and not csrf_valid(request):
        return JSONResponse({"detail": "Security check failed. Refresh the page and try again."}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Stripe-Signature", "X-LedgerStream-Signature",
                   "X-CSRF-Token"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# AWS Lambda entry point (configure handler as "lambda_function.lambda_handler").
lambda_handler = Mangum(app, lifespan="off")
