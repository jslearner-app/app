"""Bank statement pipeline: PDF -> Amazon Textract AnalyzeDocument (TABLES) -> Pandas -> ledger rows."""
import io
import os
import uuid

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pypdf import PdfReader, PdfWriter

from .money import d2

COLUMNS = ["date", "description", "reference", "withdrawal", "deposit", "balance"]
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
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


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
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        writer = PdfWriter()
        writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        yield buf.getvalue()


def analyze_with_textract(pdf_bytes: bytes) -> list:
    client = textract_client()
    blocks = []
    for page_no, page_bytes in enumerate(_split_pages(pdf_bytes), start=1):
        try:
            resp = client.analyze_document(Document={"Bytes": page_bytes}, FeatureTypes=["TABLES"])
        except ClientError as e:
            err = e.response.get("Error", {})
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
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]
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


def run_pipeline(pdf_bytes: bytes) -> list:
    return dataframe_to_rows(blocks_to_dataframe(analyze_with_textract(pdf_bytes)))


def rows_to_export(rows: list, fmt: str) -> bytes:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.columns = EXPORT_HEADERS
    if fmt == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, sheet_name="Transactions", engine="openpyxl")
        return buf.getvalue()
    return df.to_csv(index=False, float_format="%.2f").encode("utf-8")
