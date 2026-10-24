"""Running-balance reconciliation for extracted statement rows."""
from decimal import Decimal

from .money import d2


def _net(row) -> Decimal:
    return (d2(row["deposit"]) if row.get("deposit") is not None else Decimal("0")) - (
        d2(row["withdrawal"]) if row.get("withdrawal") is not None else Decimal("0"))


def reconcile(rows: list) -> dict:
    """Checks opening balance + deposits - withdrawals against each printed running balance and the closing balance."""
    first = next((i for i, r in enumerate(rows) if r.get("balance") is not None), None)
    if first is None:
        return {"status": "unavailable", "message": "No running balance column was found on this statement."}
    opening = d2(rows[first]["balance"]) - _net(rows[first])
    for r in rows[:first]:
        opening -= _net(r)
    running, mismatches = opening, []
    for idx, r in enumerate(rows):
        running += _net(r)
        if r.get("balance") is None:
            continue
        printed = d2(r["balance"])
        if printed != running:
            mismatches.append({"id": r["id"], "row": idx + 1, "date": r.get("date", ""),
                               "expected": float(running), "actual": float(printed),
                               "difference": float(printed - running)})
            running = printed
    computed_closing = opening + sum((_net(r) for r in rows), Decimal("0"))
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
        for k in ("withdrawal", "deposit", "balance"):
            r[k] = float(d2(r[k])) if r.get(k) is not None else None
    return rows
