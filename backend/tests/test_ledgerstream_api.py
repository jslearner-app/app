"""LedgerStream AI backend regression: auth, clients, statements/textract webhook, payouts, history, billing/stripe webhooks, isolation."""
import hashlib
import hmac
import io
import json
import os
import time
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

mongo = MongoClient(BE_ENV["MONGO_URL"])[BE_ENV["DB_NAME"]]


def _register(prefix="a"):
    s = requests.Session()
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"name": "TEST User", "email": email, "password": "Passw0rd!x"})
    assert r.status_code == 200, r.text
    return s, r.json()


def _cleanup_user(user_id):
    mongo.users.delete_one({"user_id": user_id})
    for c in ("clients", "statements", "payouts"):
        mongo[c].delete_many({"owner_id": user_id})
    mongo.payment_transactions.delete_many({"user_id": user_id})


@pytest.fixture(scope="module")
def user_a():
    s, u = _register("a")
    yield s, u
    _cleanup_user(u["user_id"])


@pytest.fixture(scope="module")
def user_b():
    s, u = _register("b")
    yield s, u
    _cleanup_user(u["user_id"])


@pytest.fixture(scope="module")
def client_a(user_a):
    s, _ = user_a
    r = s.post(f"{API}/clients", json={"name": "TEST_Client A", "industry": "Restaurant", "platforms": ["doordash", "bogus"]})
    assert r.status_code == 200
    return r.json()


# ---------- Auth ----------
class TestAuth:
    def test_health(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200 and r.json()["status"] == "ok"

    def test_register_sets_trial(self, user_a):
        s, u = user_a
        assert u["plan"] == "free" and u["subscription_status"] == "trial"
        assert u["pages_used"] == 0 and u["page_limit"] == 5
        assert "access_token" in s.cookies.get_dict()
        doc = mongo.users.find_one({"user_id": u["user_id"]})
        assert doc["password_hash"].startswith("$2b$")

    def test_duplicate_register(self, user_a):
        _, u = user_a
        r = requests.post(f"{API}/auth/register", json={"name": "x", "email": u["email"], "password": "Passw0rd!x"})
        assert r.status_code == 400

    def test_demo_login_and_me(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200 and r.json()["email"] == DEMO_EMAIL
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["email"] == DEMO_EMAIL

    def test_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "nope-nope"})
        assert r.status_code == 401
        mongo.login_attempts.delete_many({"identifier": {"$regex": DEMO_EMAIL}})

    def test_logout(self):
        s, u = _register("lo")
        assert s.post(f"{API}/auth/logout").status_code == 200
        s.cookies.clear()
        assert s.get(f"{API}/auth/me").status_code == 401
        _cleanup_user(u["user_id"])


# ---------- Clients CRUD ----------
class TestClients:
    def test_create_filters_platforms(self, client_a):
        assert client_a["platforms"] == ["doordash"]
        assert "_id" not in client_a

    def test_list_has_stats(self, user_a, client_a):
        s, _ = user_a
        lst = s.get(f"{API}/clients").json()
        c = next(x for x in lst if x["id"] == client_a["id"])
        assert c["statements_count"] == 0 and c["payouts_count"] == 0 and c["pages_converted"] == 0

    def test_update_and_delete(self, user_a):
        s, _ = user_a
        c = s.post(f"{API}/clients", json={"name": "TEST_Temp"}).json()
        r = s.put(f"{API}/clients/{c['id']}", json={"name": "TEST_Temp2", "industry": "Retail"})
        assert r.status_code == 200 and r.json()["name"] == "TEST_Temp2"
        assert s.delete(f"{API}/clients/{c['id']}").status_code == 200
        assert all(x["id"] != c["id"] for x in s.get(f"{API}/clients").json())

    def test_empty_name_422(self, user_a):
        s, _ = user_a
        assert s.post(f"{API}/clients", json={"name": ""}).status_code == 422


# ---------- Statements / Textract ----------
def _cell(bid, r, c, text, blocks):
    wid = f"w{bid}"
    blocks.append({"Id": wid, "BlockType": "WORD", "Text": text})
    blocks.append({"Id": bid, "BlockType": "CELL", "RowIndex": r, "ColumnIndex": c,
                   "Relationships": [{"Type": "CHILD", "Ids": [wid]}]})
    return bid


def _blocks():
    data = [["Date", "Description", "Reference/Check #", "Withdrawals", "Deposits", "Balance"],
            ["09/01/2026", "Opening deposit", "", "", "$1,000.00", "1,000.00"],
            ["09/02/2026", "Check payment", "1043", "250.50", "", "749.50"],
            ["09/03/2026", "Refund", "REF9", "(10.00)", "", "759.50"]]
    blocks, ids = [], []
    for ri, row in enumerate(data, 1):
        for ci, val in enumerate(row, 1):
            if val:
                ids.append(_cell(f"c{ri}_{ci}", ri, ci, val, blocks))
    blocks.insert(0, {"Id": "t1", "BlockType": "TABLE", "Relationships": [{"Type": "CHILD", "Ids": ids}]})
    return blocks


def _sign(body: bytes):
    return hmac.new(BE_ENV["TEXTRACT_WEBHOOK_SECRET"].encode(), body, hashlib.sha256).hexdigest()


class TestStatements:
    def test_engine_not_configured(self, user_a):
        s, _ = user_a
        r = s.get(f"{API}/statements/engine")
        assert r.status_code == 200 and r.json()["configured"] is False

    def test_convert_503_no_charge(self, user_a, client_a):
        s, u = user_a
        r = s.post(f"{API}/statements", files={"file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")},
                   data={"client_id": client_a["id"]})
        assert r.status_code == 503 and "Textract" in r.json()["detail"]
        assert s.get(f"{API}/auth/me").json()["pages_used"] == 0

    def test_webhook_invalid_sig(self):
        r = requests.post(f"{API}/webhooks/textract", data=b'{"statement_id":"x","Blocks":[]}',
                          headers={"X-LedgerStream-Signature": "bad", "Content-Type": "application/json"})
        assert r.status_code == 401

    def test_webhook_unknown_statement_404(self):
        body = json.dumps({"statement_id": "stm_nope", "Blocks": []}).encode()
        r = requests.post(f"{API}/webhooks/textract", data=body, headers={"X-LedgerStream-Signature": _sign(body)})
        assert r.status_code == 404

    def test_webhook_parse_edit_export(self, user_a, user_b, client_a):
        s, u = user_a
        sid = f"stm_test{uuid.uuid4().hex[:8]}"
        mongo.statements.insert_one({"id": sid, "kind": "statement", "owner_id": u["user_id"], "client_id": client_a["id"],
                                     "client_name": client_a["name"], "filename": "TEST_stmt.pdf", "pages": 1, "rows": [],
                                     "summary": {"transactions": 0}, "created_at": datetime.now(timezone.utc).isoformat()})
        body = json.dumps({"statement_id": sid, "Blocks": _blocks()}).encode()
        r = requests.post(f"{API}/webhooks/textract", data=body, headers={"X-LedgerStream-Signature": _sign(body)})
        assert r.status_code == 200 and r.json()["transactions"] == 3, r.text
        doc = s.get(f"{API}/statements/{sid}").json()
        rows = doc["rows"]
        assert rows[0]["deposit"] == 1000.0 and rows[1]["reference"] == "1043" and rows[1]["withdrawal"] == 250.5
        assert rows[2]["withdrawal"] == -10.0
        assert doc["summary"]["closing_balance"] == 759.5
        rows[0]["description"] = "Edited desc"
        rows[0]["deposit"] = 1000.005
        r = s.put(f"{API}/statements/{sid}/rows", json={"rows": rows})
        assert r.status_code == 200 and r.json()["rows"][0]["description"] == "Edited desc"
        assert s.get(f"{API}/statements/{sid}").json()["rows"][0]["description"] == "Edited desc"
        csv = s.get(f"{API}/statements/{sid}/export?fmt=csv")
        assert csv.status_code == 200 and csv.text.splitlines()[0] == "Date,Description,Reference/Check #,Withdrawals,Deposits,Balance"
        xl = s.get(f"{API}/statements/{sid}/export?fmt=xlsx")
        assert xl.status_code == 200 and xl.content[:2] == b"PK"
        # isolation
        sb, _ = user_b
        assert sb.get(f"{API}/statements/{sid}").status_code == 404
        assert sb.put(f"{API}/statements/{sid}/rows", json={"rows": []}).status_code == 404
        assert sb.get(f"{API}/statements/{sid}/export").status_code == 404
        assert sb.delete(f"{API}/history/statement/{sid}").status_code == 404
        hist = s.get(f"{API}/history?kind=statement").json()
        assert any(h["id"] == sid for h in hist) and all(h["kind"] == "statement" for h in hist)
        assert s.delete(f"{API}/history/statement/{sid}").status_code == 200
        assert s.get(f"{API}/statements/{sid}").status_code == 404


# ---------- Payouts ----------
class TestPayouts:
    def _upload(self, s, client_id, content, platform="doordash", rate="30"):
        return s.post(f"{API}/payouts", files={"file": ("p.csv", content, "text/csv")},
                      data={"client_id": client_id, "platform": platform, "commission_rate": rate})

    def test_all_samples_balanced(self, user_a, client_a):
        s, _ = user_a
        for p in ["toast", "doordash", "ubereats", "shopify", "stripe"]:
            csv = s.get(f"{API}/payouts/sample/{p}")
            assert csv.status_code == 200
            r = self._upload(s, client_a["id"], csv.content, platform=p)
            assert r.status_code == 200, (p, r.text)
            led = r.json()["ledger"]
            assert led["balanced"] and led["total_debits"] == led["total_credits"]

    def test_doordash_numbers_recalc_qbo_isolation(self, user_a, user_b, client_a):
        s, _ = user_a
        csv = s.get(f"{API}/payouts/sample/doordash").content
        d = self._upload(s, client_a["id"], csv).json()
        assert d["gross_total"] == 272.65
        lines = {l["account"]: l for l in d["ledger"]["lines"]}
        assert lines["Delivery Commissions Expense"]["debit"] == 81.8
        assert lines["Bank Clearing Account"]["debit"] == 190.85
        assert lines["Gross Sales Revenue"]["credit"] == 272.65
        r = s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 15})
        led = r.json()["ledger"]
        assert led["balanced"] and led["lines"][1]["debit"] == 40.9 and led["lines"][0]["debit"] == 231.75
        assert s.get(f"{API}/payouts/{d['id']}").json()["commission_rate"] == 15
        assert s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 101}).status_code == 422
        q = s.get(f"{API}/payouts/{d['id']}/qbo")
        assert q.status_code == 200
        assert q.text.splitlines()[0] == "Journal No,Journal Date,Account,Debits,Credits,Description,Name,Memo"
        sb, _ = user_b
        assert sb.get(f"{API}/payouts/{d['id']}").status_code == 404
        assert sb.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 10}).status_code == 404
        assert sb.get(f"{API}/payouts/{d['id']}/qbo").status_code == 404
        assert sb.delete(f"{API}/history/payout/{d['id']}").status_code == 404
        assert s.delete(f"{API}/history/payout/{d['id']}").status_code == 200

    def test_edge_cases(self, user_a, user_b, client_a):
        s, _ = user_a
        assert self._upload(s, client_a["id"], b"foo,bar\nabc,def\n").status_code == 400
        assert self._upload(s, client_a["id"], b"\x00\x01\x02").status_code == 400
        assert self._upload(s, client_a["id"], b"").status_code == 400
        assert self._upload(s, client_a["id"], b"Subtotal\n10\n", rate="150").status_code in (400, 422)
        assert self._upload(s, client_a["id"], b"Subtotal\n10\n", platform="grubhub").status_code == 400
        sb, _ = user_b
        assert self._upload(sb, client_a["id"], b"Subtotal\n10\n").status_code == 404
        assert sb.put(f"{API}/clients/{client_a['id']}", json={"name": "hack"}).status_code == 404
        assert sb.delete(f"{API}/clients/{client_a['id']}").status_code == 404

    def test_history_filters(self, user_a, client_a):
        s, _ = user_a
        h = s.get(f"{API}/history?kind=payout&client_id={client_a['id']}").json()
        assert len(h) >= 5 and all(x["kind"] == "payout" and x["client_id"] == client_a["id"] for x in h)
        assert s.get(f"{API}/history?client_id=cli_none").json() == []


# ---------- Billing / Stripe ----------
def _stripe_sig(payload: str):
    t = str(int(time.time()))
    v1 = hmac.new(BE_ENV["STRIPE_WEBHOOK_SECRET"].encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


def _event(etype, obj):
    return json.dumps({"id": f"evt_test_{uuid.uuid4().hex[:8]}", "object": "event", "type": etype,
                       "data": {"object": obj}, "api_version": "2024-06-20", "created": int(time.time())})


class TestBilling:
    def test_summary_and_portal_disabled(self, user_a):
        s, _ = user_a
        b = s.get(f"{API}/billing/summary").json()
        assert b["plan"] == "free" and b["has_portal"] is False
        assert s.post(f"{API}/billing/portal", json={"origin_url": BASE_URL}).status_code == 400

    def test_checkout_creates_stripe_session(self, user_a):
        s, _ = user_a
        r = s.post(f"{API}/payments/checkout", json={"plan": "starter", "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://checkout.stripe.com")
        st = requests.get(f"{API}/payments/status/{r.json()['session_id']}").json()
        assert st["payment_status"] == "pending" and st["plan"] == "starter"
        assert s.post(f"{API}/payments/checkout", json={"plan": "gold", "origin_url": BASE_URL}).status_code == 400

    def test_webhook_invalid_signature(self):
        for path in ("/webhooks/stripe", "/stripe/webhook"):
            r = requests.post(f"{API}{path}", data="{}", headers={"Stripe-Signature": "t=1,v1=bad"})
            assert r.status_code == 400

    def test_signed_webhook_lifecycle(self):
        s, u = _register("wh")
        try:
            sess_id = f"cs_test_{uuid.uuid4().hex[:16]}"
            mongo.payment_transactions.insert_one({"session_id": sess_id, "user_id": u["user_id"], "plan": "agency",
                                                   "status": "initiated", "payment_status": "pending"})
            sub_id, cus_id = f"sub_test_{uuid.uuid4().hex[:8]}", f"cus_test_{uuid.uuid4().hex[:8]}"
            p = _event("checkout.session.completed", {"id": sess_id, "object": "checkout.session", "payment_status": "paid",
                                                      "status": "complete", "subscription": sub_id, "customer": cus_id})
            r = requests.post(f"{API}/webhooks/stripe", data=p, headers={"Stripe-Signature": _stripe_sig(p), "Content-Type": "application/json"})
            assert r.status_code == 200, r.text
            me = s.get(f"{API}/auth/me").json()
            assert me["plan"] == "agency" and me["subscription_status"] == "active_subscriber" and me["page_limit"] is None
            assert s.get(f"{API}/billing/summary").json()["has_portal"] is True
            p = _event("customer.subscription.deleted", {"id": sub_id, "object": "subscription", "customer": cus_id})
            r = requests.post(f"{API}/stripe/webhook", data=p, headers={"Stripe-Signature": _stripe_sig(p), "Content-Type": "application/json"})
            assert r.status_code == 200
            me = s.get(f"{API}/auth/me").json()
            assert me["plan"] == "free" and me["subscription_status"] == "trial"
        finally:
            _cleanup_user(u["user_id"])
