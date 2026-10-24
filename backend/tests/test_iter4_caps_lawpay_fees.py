"""Iteration 4: monthly page caps (starter 200 / agency 1000 / free 5 lifetime), LawPay real fee column, standalone /app/api."""
import io
import os
import sys
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
PERIOD = datetime.now(timezone.utc).strftime("%Y-%m")

mongo = MongoClient(BE_ENV["MONGO_URL"])[BE_ENV["DB_NAME"]]


def set_user(**fields):
    unset = {k: "" for k, v in fields.items() if v is None}
    upd = {"$set": {k: v for k, v in fields.items() if v is not None}}
    if unset:
        upd["$unset"] = unset
    mongo.users.update_one({"email": DEMO_EMAIL}, upd)


def reset_demo():
    mongo.users.update_one({"email": DEMO_EMAIL}, {"$set": {"plan": "free", "subscription_status": "trial", "pages_used": 0},
                                                    "$unset": {"usage_period": "", "period_pages": ""}})


@pytest.fixture(scope="module")
def demo():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    user = r.json().get("user", r.json())
    clients = s.get(f"{API}/clients").json()
    created = []
    yield s, user, clients[0]["id"], created
    for p in created:
        mongo.payouts.delete_one({"id": p})
    reset_demo()


def me(s):
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json().get("user", r.json())


def upload_pdf(s, client_id):
    with open(SAMPLE_PDF, "rb") as f:
        return s.post(f"{API}/statements", files={"file": ("sample_statement.pdf", f, "application/pdf")},
                      data={"client_id": client_id}, timeout=90)


def db_user():
    return mongo.users.find_one({"email": DEMO_EMAIL}, {"_id": 0})


# --- /auth/me usage fields
class TestMeFields:
    def test_free(self, demo):
        s, *_ = demo
        reset_demo(); set_user(pages_used=2)
        u = me(s)
        assert u["usage_pages"] == 2 and u["page_limit"] == 5 and u["limit_period"] == "trial" and u["period_resets_at"] is None

    def test_starter(self, demo):
        s, *_ = demo
        set_user(plan="starter", subscription_status="active_subscriber", usage_period=PERIOD, period_pages=150)
        u = me(s)
        assert u["usage_pages"] == 150 and u["page_limit"] == 200 and u["limit_period"] == "month"
        n = datetime.now(timezone.utc)
        exp = datetime(n.year + (n.month == 12), n.month % 12 + 1, 1).date().isoformat()
        assert u["period_resets_at"] == exp

    def test_starter_stale_period_shows_zero(self, demo):
        s, *_ = demo
        set_user(usage_period="2000-01", period_pages=200)
        assert me(s)["usage_pages"] == 0

    def test_agency(self, demo):
        s, *_ = demo
        set_user(plan="agency", usage_period=PERIOD, period_pages=1000)
        u = me(s)
        assert u["page_limit"] == 1000 and u["usage_pages"] == 1000


# --- caps enforcement on POST /statements
class TestCaps:
    def test_starter_at_200_402(self, demo):
        s, _, cid, _ = demo
        set_user(plan="starter", usage_period=PERIOD, period_pages=200)
        r = upload_pdf(s, cid)
        assert r.status_code == 402, r.text
        assert "Monthly page limit reached" in r.json()["detail"]
        assert db_user()["period_pages"] == 200

    def test_agency_at_1000_402(self, demo):
        s, _, cid, _ = demo
        set_user(plan="agency", usage_period=PERIOD, period_pages=1000)
        r = upload_pdf(s, cid)
        assert r.status_code == 402 and "Agency" in r.json()["detail"]

    def test_free_at_5_402(self, demo):
        s, _, cid, _ = demo
        reset_demo(); set_user(pages_used=5)
        r = upload_pdf(s, cid)
        assert r.status_code == 402 and "Free trial limit reached" in r.json()["detail"]

    def test_starter_199_reserves_then_refunds(self, demo):
        s, _, cid, _ = demo
        set_user(plan="starter", subscription_status="active_subscriber", pages_used=10, usage_period=PERIOD, period_pages=199)
        r = upload_pdf(s, cid)
        assert r.status_code == 424, r.text  # Textract denied by AWS SCP
        u = db_user()
        assert u["period_pages"] == 199 and u["pages_used"] == 10

    def test_stale_period_resets(self, demo):
        s, _, cid, _ = demo
        set_user(plan="starter", usage_period="2000-01", period_pages=200, pages_used=10)
        r = upload_pdf(s, cid)
        assert r.status_code == 424, r.text
        u = db_user()
        assert u["usage_period"] == PERIOD and u["period_pages"] == 0


# --- LawPay fee column
class TestLawPay:
    def test_lawpay_split(self, demo):
        s, _, cid, created = demo
        csv = s.get(f"{API}/payouts/sample/lawpay").content
        r = s.post(f"{API}/payouts", files={"file": ("lp.csv", csv, "text/csv")},
                   data={"client_id": cid, "platform": "lawpay", "commission_rate": "3"})
        assert r.status_code == 200, r.text
        d = r.json(); created.append(d["id"])
        assert d["fee_total"] == 272.88 and d["fee_line_items"] == 3 and d["fee_column"] == "Fee"
        led = d["ledger"]
        amounts = {(l["account"], l["side"]): (l["debit"] or l["credit"]) for l in led["lines"]}
        assert amounts[("Trust Bank Account (IOLTA)", "debit")] == 9250.0
        assert amounts[("Client Trust Liability", "credit")] == 9250.0
        assert amounts[("Credit Card Processing Fees", "debit")] == 272.88
        assert amounts[("Operating Bank Account", "credit")] == 272.88
        assert led["total_debits"] == led["total_credits"] == 9522.88 and led["balanced"]
        qbo = s.get(f"{API}/payouts/{d['id']}/qbo").text
        assert "272.88" in qbo
        rr = s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 5})
        assert rr.status_code == 400

    def test_lawpay_negative_and_parenthesized_fees(self, demo):
        s, _, cid, created = demo
        csv = b"Date,Amount,Fee\n2026-09-01,100.00,-2.50\n2026-09-02,200.00,(3.25)\n2026-09-03,50,$1.00\n"
        r = s.post(f"{API}/payouts", files={"file": ("lp.csv", csv, "text/csv")}, data={"client_id": cid, "platform": "lawpay"})
        assert r.status_code == 200, r.text
        created.append(r.json()["id"])
        assert r.json()["fee_total"] == 6.75

    def test_lawpay_no_fee_column(self, demo):
        s, _, cid, _ = demo
        csv = b"Date,Amount,Net Deposit\n2026-09-01,100.00,100.00\n"
        r = s.post(f"{API}/payouts", files={"file": ("lp.csv", csv, "text/csv")}, data={"client_id": cid, "platform": "lawpay"})
        assert r.status_code == 400 and "Could not find a fee column" in r.json()["detail"]

    def test_doordash_regression(self, demo):
        s, _, cid, created = demo
        csv = s.get(f"{API}/payouts/sample/doordash").content
        r = s.post(f"{API}/payouts", files={"file": ("dd.csv", csv, "text/csv")},
                   data={"client_id": cid, "platform": "doordash", "commission_rate": "30"})
        assert r.status_code == 200
        d = r.json(); created.append(d["id"])
        comm = [l for l in d["ledger"]["lines"] if l["account"] == "Delivery Commissions Expense"][0]["debit"]
        assert comm == 81.80 and d["ledger"]["balanced"]
        rr = s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 20})
        assert rr.status_code == 200 and rr.json()["ledger"]["balanced"]
        assert s.get(f"{API}/payouts/{d['id']}").json()["commission_rate"] == 20


# --- standalone /app/api
def test_standalone_api_lawpay(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://x.test")
    monkeypatch.setenv("LEDGERSTREAM_API_KEY", "k")
    sys.path.insert(0, "/app/api")
    from fastapi.testclient import TestClient
    import importlib
    import index
    importlib.reload(index)
    from ledgerstream_core.payouts import SAMPLE_CSV
    c = TestClient(index.app)
    r = c.post("/api/payouts/split", files={"file": ("lp.csv", SAMPLE_CSV["lawpay"].encode(), "text/csv")},
               data={"platform": "lawpay"}, headers={"X-API-Key": "k", "Authorization": "Bearer k"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fee_total"] == 272.88 and d["ledger"]["balanced"]
