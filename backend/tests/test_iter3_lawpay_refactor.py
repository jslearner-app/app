"""Iteration 3: LawPay trust splitter, refactor regression (ledgerstream_core), Textract AccessDenied, CORS, standalone /app/api."""
import csv
import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

FE_ENV = dotenv_values("/app/frontend/.env")
BE_ENV = dotenv_values("/app/backend/.env")
BASE_URL = FE_ENV["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
DEMO_EMAIL = "demo@ledgerstream.ai"
DEMO_PASSWORD = "LedgerDemo#2026"
SAMPLE_PDF = Path(__file__).parent / "sample_statement.pdf"

mongo = MongoClient(BE_ENV["MONGO_URL"])[BE_ENV["DB_NAME"]]


@pytest.fixture(scope="module")
def demo():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    user = r.json().get("user", r.json())
    created = {"payouts": [], "statements": [], "clients": []}
    yield s, user, created
    for p in created["payouts"]:
        mongo.payouts.delete_one({"id": p})
    for st in created["statements"]:
        mongo.statements.delete_one({"id": st})
    for c in created["clients"]:
        mongo.clients.delete_one({"id": c})
    mongo.users.update_one({"email": DEMO_EMAIL}, {"$set": {"pages_used": 0}})


@pytest.fixture(scope="module")
def demo_client(demo):
    s, _, created = demo
    r = s.post(f"{API}/clients", json={"name": "TEST_LawFirm", "industry": "Legal", "platforms": ["lawpay", "bogus"]})
    assert r.status_code == 200, r.text
    created["clients"].append(r.json()["id"])
    return r.json()


# ---------- Auth ----------
class TestAuth:
    def test_login_me(self, demo):
        s, user, _ = demo
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["email"] == DEMO_EMAIL


# ---------- Clients (LawPay toggle) ----------
class TestClients:
    def test_lawpay_saved_and_bogus_filtered(self, demo, demo_client):
        s, _, _ = demo
        assert demo_client["platforms"] == ["lawpay"]
        lst = s.get(f"{API}/clients").json()
        c = next(c for c in lst if c["id"] == demo_client["id"])
        assert c["platforms"] == ["lawpay"]
        r = s.put(f"{API}/clients/{demo_client['id']}", json={"name": "TEST_LawFirm2", "platforms": ["lawpay", "stripe"]})
        assert r.status_code == 200 and r.json()["platforms"] == ["lawpay", "stripe"]


# ---------- Payouts ----------
class TestPayouts:
    def _split(self, s, cid, platform, rate):
        csv_text = s.get(f"{API}/payouts/sample/{platform}").text
        return s.post(f"{API}/payouts", files={"file": (f"sample_{platform}.csv", csv_text, "text/csv")},
                      data={"client_id": cid, "platform": platform, "commission_rate": str(rate)})

    def test_lawpay_trust_ledger(self, demo, demo_client):
        s, _, created = demo
        r = self._split(s, demo_client["id"], "lawpay", 3)
        assert r.status_code == 200, r.text
        d = r.json()
        created["payouts"].append(d["id"])
        assert d["gross_total"] == 9250.0
        lines = [(l["account"], l["debit"], l["credit"]) for l in d["ledger"]["lines"]]
        assert lines == [("Trust Bank Account (IOLTA)", 9250.0, 0.0), ("Client Trust Liability", 0.0, 9250.0),
                         ("Credit Card Processing Fees", 277.5, 0.0), ("Operating Bank Account", 0.0, 277.5)]
        assert d["ledger"]["total_debits"] == 9527.5 == d["ledger"]["total_credits"] and d["ledger"]["balanced"]
        # recalc
        r2 = s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 2.5})
        assert r2.status_code == 200 and r2.json()["ledger"]["lines"][2]["debit"] == 231.25
        assert s.get(f"{API}/payouts/{d['id']}").json()["commission_rate"] == 2.5
        q = s.get(f"{API}/payouts/{d['id']}/qbo")
        assert q.status_code == 200
        rows = list(csv.reader(io.StringIO(q.text)))
        assert rows[0][:5] == ["Journal No", "Journal Date", "Account", "Debits", "Credits"] and len(rows) == 5
        assert "LawPay payout split" in rows[1][5]

    def test_doordash_regression(self, demo, demo_client):
        s, _, created = demo
        r = self._split(s, demo_client["id"], "doordash", 30)
        assert r.status_code == 200, r.text
        d = r.json()
        created["payouts"].append(d["id"])
        lines = d["ledger"]["lines"]
        assert len(lines) == 3 and d["gross_total"] == 272.65
        assert lines[0]["debit"] == 190.85 and lines[1]["debit"] == 81.8 and lines[2]["credit"] == 272.65
        assert d["ledger"]["balanced"]


# ---------- Statements (seeded) ----------
class TestStatements:
    def test_put_rows_recompute_export_history(self, demo, demo_client):
        s, user, created = demo
        sid = f"stm_TEST{uuid.uuid4().hex[:8]}"
        rows = [
            {"id": "r1", "date": "09/01", "description": "Open", "reference": "", "withdrawal": None, "deposit": 100.0, "balance": 1100.0},
            {"id": "r2", "date": "09/02", "description": "Chk", "reference": "1043", "withdrawal": 50.0, "deposit": None, "balance": 1050.0},
        ]
        mongo.statements.insert_one({"id": sid, "kind": "statement", "owner_id": user["user_id"], "client_id": demo_client["id"],
                                     "client_name": demo_client["name"], "filename": "TEST_stmt.pdf", "pages": 1, "rows": rows,
                                     "summary": {"transactions": 2, "reconciliation": {"status": "reconciled"}},
                                     "created_at": datetime.now(timezone.utc).isoformat()})
        created["statements"].append(sid)
        base_count = s.get(f"{API}/history/review-count").json()["needs_review"]
        rows[1]["withdrawal"] = 60.004  # creates mismatch + rounding
        r = s.put(f"{API}/statements/{sid}/rows", json={"rows": rows})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["rows"][1]["withdrawal"] == 60.0
        rec = d["summary"]["reconciliation"]
        assert rec["status"] == "mismatch" and rec["mismatched_rows"][0]["difference"] == 10.0
        assert s.get(f"{API}/history/review-count").json()["needs_review"] == base_count + 1
        nr = s.get(f"{API}/history?kind=needs_review").json()
        assert any(h["id"] == sid for h in nr) and all("rows" not in h for h in nr)
        assert any(h["id"] == sid for h in s.get(f"{API}/history").json())
        c = s.get(f"{API}/statements/{sid}/export?fmt=csv")
        assert c.status_code == 200 and c.text.splitlines()[0].startswith("Date,Description")
        assert "60.00" in c.text
        x = s.get(f"{API}/statements/{sid}/export?fmt=xlsx")
        assert x.status_code == 200 and x.content[:2] == b"PK"

    def test_engine_configured(self, demo):
        s, _, _ = demo
        r = s.get(f"{API}/statements/engine")
        assert r.status_code == 200 and r.json()["configured"] is True

    def test_textract_access_denied_refund(self, demo, demo_client):
        s, _, _ = demo
        mongo.users.update_one({"email": DEMO_EMAIL}, {"$set": {"pages_used": 0}})
        with open(SAMPLE_PDF, "rb") as f:
            r = s.post(f"{API}/statements", files={"file": ("sample_statement.pdf", f, "application/pdf")},
                       data={"client_id": demo_client["id"]}, timeout=90)
        print("UPLOAD:", r.status_code, r.text[:300])
        assert r.status_code == 502
        assert "Textract rejected page 1: AccessDeniedException" in r.json()["detail"]
        assert s.get(f"{API}/auth/me").json()["pages_used"] == 0


# ---------- Billing ----------
class TestBilling:
    def test_summary(self, demo):
        s, _, _ = demo
        r = s.get(f"{API}/billing/summary")
        assert r.status_code == 200, r.text

    def test_checkout(self, demo):
        s, _, _ = demo
        r = s.post(f"{API}/payments/checkout", json={"plan": "starter", "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://checkout.stripe.com")

    def test_stripe_webhook_bad_sig(self):
        r = requests.post(f"{API}/webhooks/stripe", data=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"})
        assert r.status_code == 400


# ---------- CORS ----------
class TestCors:
    def test_preflight(self):
        r = requests.options(f"{API}/clients", headers={"Origin": "https://x.test", "Access-Control-Request-Method": "PUT",
                                                        "Access-Control-Request-Headers": "content-type"})
        print(dict(r.headers))
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-methods") == "GET, POST, PUT, DELETE, OPTIONS"
        assert r.headers.get("access-control-allow-credentials") == "true"


# ---------- Standalone /app/api ----------
@pytest.fixture(scope="module")
def standalone():
    os.environ["CORS_ORIGINS"] = "https://x.test"
    os.environ["LEDGERSTREAM_API_KEY"] = "k"
    sys.path.insert(0, "/app/api")
    import importlib
    import index
    importlib.reload(index)
    from fastapi.testclient import TestClient
    return TestClient(index.app)


class TestStandalone:
    def test_health(self, standalone):
        r = standalone.get("/api/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"

    def test_no_key_401(self, standalone):
        r = standalone.post("/api/payouts/split", files={"file": ("a.csv", b"a,b\n1,2\n")}, data={"platform": "doordash"})
        assert r.status_code == 401

    def test_doordash_and_lawpay_qbo(self, standalone):
        sys.path.insert(0, "/app/api")
        from ledgerstream_core.payouts import SAMPLE_CSV
        h = {"X-API-Key": "k"}
        r = standalone.post("/api/payouts/split", headers=h, files={"file": ("dd.csv", SAMPLE_CSV["doordash"].encode())},
                            data={"platform": "doordash", "commission_rate": "30"})
        assert r.status_code == 200 and r.json()["ledger"]["balanced"] and r.json()["ledger"]["total_credits"] == 272.65
        r = standalone.post("/api/payouts/split", headers=h, files={"file": ("lp.csv", SAMPLE_CSV["lawpay"].encode())},
                            data={"platform": "lawpay", "commission_rate": "3", "format": "qbo"})
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert "Trust Bank Account (IOLTA)" in r.text and "277.50" in r.text

    def test_reconcile_mismatch(self, standalone):
        rows = [{"id": "a", "date": "1", "deposit": 100, "balance": 100},
                {"id": "b", "date": "2", "withdrawal": 10, "balance": 95}]
        r = standalone.post("/api/statements/reconcile", headers={"X-API-Key": "k"}, json={"rows": rows})
        assert r.status_code == 200 and r.json()["reconciliation"]["status"] == "mismatch"

    def test_convert_non_pdf_400(self, standalone):
        r = standalone.post("/api/statements/convert", headers={"X-API-Key": "k"}, files={"file": ("a.txt", b"hello")})
        assert r.status_code == 400

    def test_convert_pdf_ext_but_garbage_400(self, standalone):
        r = standalone.post("/api/statements/convert", headers={"X-API-Key": "k"}, files={"file": ("a.pdf", b"garbage")})
        assert r.status_code == 400
