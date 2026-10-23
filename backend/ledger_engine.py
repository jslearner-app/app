"""Merchant payout splitter: platform CSV -> gross/net detection -> balanced double-entry matrix."""
import io
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

CENT = Decimal("0.01")
PLATFORMS = ["toast", "doordash", "ubereats", "shopify", "stripe"]
GROSS_KEYWORDS = ("gross", "subtotal", "sales", "order total", "amount", "total")
NET_KEYWORDS = ("net", "payout", "deposit")
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
}


def d2(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


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


def parse_platform_csv(raw: bytes) -> dict:
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
    return {
        "rows_parsed": int(len(df)),
        "gross_column": str(gross_col),
        "net_column": str(net_col) if net_col is not None else None,
        "gross_total": float(_sum(df[gross_col])),
        "file_net_total": float(_sum(df[net_col])) if net_col is not None else None,
    }


def build_ledger(gross_total: float, commission_rate: float) -> dict:
    gross = d2(gross_total)
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
    total_credits = gross
    return {
        "lines": lines,
        "total_debits": float(total_debits),
        "total_credits": float(total_credits),
        "difference": float(total_debits - total_credits),
        "balanced": total_debits == total_credits,
    }


def ledger_to_qbo_csv(payout: dict) -> bytes:
    journal_no = f"LS-{payout['id'][-6:].upper()}"
    journal_date = date.today().strftime("%m/%d/%Y")
    desc = f"{payout['platform'].title()} payout split - {payout['filename']}"
    rows = [
        [journal_no, journal_date, line["account"],
         f"{line['debit']:.2f}" if line["debit"] else "",
         f"{line['credit']:.2f}" if line["credit"] else "",
         desc, payout.get("client_name", ""), line["memo"]]
        for line in payout["ledger"]["lines"]
    ]
    return pd.DataFrame(rows, columns=QBO_HEADERS).to_csv(index=False).encode("utf-8")
