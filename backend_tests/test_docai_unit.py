# Iteration 11: Unit tests for the Document AI pipeline (entities_to_dataframe, statement_totals, _reconcile_totals,
# run_docai_diagnostic paths, docai_failure classification, 15-page cap via ASGI) and _connect_database fallback
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from dotenv import load_dotenv
from google.api_core import exceptions as gexc

load_dotenv("/app/backend/.env")
sys.path.insert(0, str(Path("/app/api")))

import lambda_function as lf  # noqa: E402


def prop(t, text):
    return NS(type_=t, mention_text=text)


def item(**props):
    return NS(type_="table_item", mention_text="raw text", properties=[prop(k, v) for k, v in props.items()])


def doc(entities):
    return NS(entities=entities)


SAMPLE = doc([
    NS(type_="starting_balance", mention_text="$1,000.00", properties=[]),
    item(transaction_deposit_date="09/01/2026", transaction_deposit_description="Opening  deposit",
         transaction_deposit="1,000.00", balance="2,000.00"),
    item(transaction_withdrawal_date="09/02/2026", transaction_withdrawal_description="Office supplies",
         transaction_withdrawal="(150.25)", check_number="1001", balance="1,849.75"),
    item(transaction_deposit_description="no date row"),
    NS(type_="ending_balance", mention_text="1,849.75", properties=[]),
])


def test_entities_to_dataframe():
    rows = lf.dataframe_to_rows(lf.entities_to_dataframe(SAMPLE))
    assert len(rows) == 2
    assert rows[0]["date"] == "09/01/2026" and rows[0]["description"] == "Opening deposit"
    assert rows[0]["deposit"] == 1000.0 and rows[0]["withdrawal"] is None and rows[0]["balance"] == 2000.0
    assert rows[1]["withdrawal"] == 150.25 and rows[1]["reference"] == "1001" and rows[1]["deposit"] is None


def test_statement_totals():
    assert lf.statement_totals(SAMPLE) == {"starting_balance": 1000.0, "ending_balance": 1849.75}
    assert lf.statement_totals(doc([])) == {"starting_balance": None, "ending_balance": None}


def test_reconcile_totals_without_balances():
    rows = [{"id": "a", "deposit": 100.0, "withdrawal": None, "balance": None},
            {"id": "b", "deposit": None, "withdrawal": 30.0, "balance": None}]
    ok = lf.reconcile(rows, {"starting_balance": 50.0, "ending_balance": 120.0})
    assert ok["status"] == "reconciled" and ok["computed_closing"] == 120.0
    bad = lf.reconcile(rows, {"starting_balance": 50.0, "ending_balance": 125.0})
    assert bad["status"] == "mismatch" and bad["difference"] == 5.0
    assert lf.reconcile(rows, {"starting_balance": None, "ending_balance": 1})["status"] == "unavailable"
    assert lf.summarize(rows, {"starting_balance": 50.0, "ending_balance": 120.0})["closing_balance"] == 120.0


def test_diagnostic_not_configured(monkeypatch):
    for k in ("GOOGLE_APPLICATION_CREDENTIALS_JSON", "DOCUMENTAI_LOCATION", "DOCUMENTAI_PROCESSOR_ID"):
        monkeypatch.delenv(k, raising=False)
    res = lf.run_docai_diagnostic()
    assert res["status"] == "not_configured" and [s["id"] for s in res["steps"]] == ["config"]


def _configure(monkeypatch, creds="{}"):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", creds)
    monkeypatch.setenv("DOCUMENTAI_LOCATION", "us")
    monkeypatch.setenv("DOCUMENTAI_PROCESSOR_ID", "proc123")
    lf._docai_cache.clear()


def test_diagnostic_invalid_credentials(monkeypatch):
    _configure(monkeypatch, "not json")
    res = lf.run_docai_diagnostic()
    assert res["status"] == "invalid_credentials" and [s["ok"] for s in res["steps"]] == [True, False]


def test_diagnostic_ready_and_mismatch(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(lf, "docai_client", lambda: (None, "projects/p/locations/us/processors/proc123", "sa@p.iam"))
    monkeypatch.setattr(lf, "process_with_docai", lambda b: SAMPLE)
    res = lf.run_docai_diagnostic()
    assert res["status"] == "ready" and [s["id"] for s in res["steps"]] == ["config", "credentials", "processing", "pipeline"]
    assert all(s["ok"] for s in res["steps"])
    monkeypatch.setattr(lf, "process_with_docai", lambda b: doc([]))
    assert lf.run_docai_diagnostic()["status"] == "parse_mismatch"

    def boom(b):
        raise lf.DocumentAIError(*lf.docai_failure(gexc.PermissionDenied("nope")))
    monkeypatch.setattr(lf, "process_with_docai", boom)
    res = lf.run_docai_diagnostic()
    assert res["status"] == "permission_denied" and res["steps"][-1]["ok"] is False


def test_docai_failure_classification():
    assert lf.docai_failure(gexc.PermissionDenied("x"))[0] == "permission_denied"
    assert lf.docai_failure(gexc.NotFound("x"))[0] == "processor_not_found"
    assert lf.docai_failure(gexc.Unauthenticated("x"))[0] == "invalid_credentials"
    assert lf.docai_failure(gexc.ServiceUnavailable("x"))[0] == "unreachable"
    assert lf.docai_failure(gexc.InvalidArgument("bad"))[0] == "docai_error"


def test_connect_database_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    c, d = lf._connect_database()
    assert d.name == os.environ["DB_NAME"]
    monkeypatch.setenv("DATABASE_URL", os.environ["MONGO_URL"])
    c2, d2 = lf._connect_database()
    assert d2.name == os.environ["DB_NAME"]


# 16-page PDF -> 400 (once configured), pages not charged; 15-page passes the cap (pipeline faked)
def test_page_cap_15_in_process(monkeypatch):
    import uuid
    from fastapi.testclient import TestClient
    from pymongo import MongoClient
    from test_ledgerstream_regression import blank_pdf
    _configure(monkeypatch)
    monkeypatch.setattr(lf, "run_statement_pipeline", lambda raw: ([], {"starting_balance": None, "ending_balance": None}))
    mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    uid = f"user_test{uuid.uuid4().hex[:8]}"
    mdb.users.insert_one({"user_id": uid, "email": f"{uid}@example.com", "name": "TEST cap", "plan": "agency",
                          "subscription_status": "active_subscriber", "pages_used": 0})
    mdb.clients.insert_one({"id": f"cli_{uid}", "owner_id": uid, "name": "TEST_cap"})
    try:
        with TestClient(lf.app, base_url="https://testserver") as tc:
            tc.headers["Authorization"] = "Bearer " + lf.create_access_token(uid, f"{uid}@example.com")
            r = tc.post("/api/statements", data={"client_id": f"cli_{uid}"},
                        files={"file": ("TEST_16.pdf", blank_pdf(16), "application/pdf")})
            assert r.status_code == 400 and "up to 15 pages" in r.json()["detail"], r.text
            assert mdb.users.find_one({"user_id": uid})["pages_used"] == 0
            r = tc.post("/api/statements", data={"client_id": f"cli_{uid}"},
                        files={"file": ("TEST_15.pdf", blank_pdf(15), "application/pdf")})
            assert r.status_code == 200 and r.json()["pages"] == 15 and r.json()["engine"] == "google_document_ai", r.text
    finally:
        mdb.statements.delete_many({"owner_id": uid})
        mdb.clients.delete_many({"owner_id": uid})
        mdb.users.delete_one({"user_id": uid})
