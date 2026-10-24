# Regression suite for LedgerStream AI after Lambda refactor (/app/api/lambda_function.py)
import io
import os
import uuid

import pytest
import requests
from pymongo import MongoClient
from pypdf import PdfWriter


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env("/app/frontend/.env", "REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
DEMO = {"email": "demo@ledgerstream.ai", "password": "LedgerDemo#2026"}
mdb = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]


def blank_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


@pytest.fixture(scope="module")
def demo():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=DEMO)
    if r.status_code != 200:
        pytest.skip(f"demo login failed {r.status_code} {r.text}")
    s.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    yield s
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0, "plan": "free", "subscription_status": "trial"}})


@pytest.fixture(scope="module")
def demo_client(demo):
    r = demo.post(f"{API}/clients", json={"name": "TEST_PayoutClient", "platforms": ["toast", "bogus"]})
    assert r.status_code == 200
    c = r.json()
    yield c
    demo.delete(f"{API}/clients/{c['id']}")
    mdb.payouts.delete_many({"client_id": c["id"]})
    mdb.statements.delete_many({"client_id": c["id"]})


# ---------- Health / auth ----------
def test_health():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert requests.get(f"{API}/").json()["service"] == "LedgerStream AI"


def test_login_cookies_and_me(demo):
    r = requests.post(f"{API}/auth/login", json=DEMO)
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "access_token" in sc and "HttpOnly" in sc and "refresh_token" in sc
    me = demo.get(f"{API}/auth/me").json()
    assert me["email"] == DEMO["email"] and me["plan"] == "free" and me["page_limit"] == 5
    assert isinstance(me["low_page_alert"], bool)


def test_low_page_alert_threshold(demo):
    uid = {"email": DEMO["email"]}
    try:
        for used, expected in [(3, False), (4, True), (5, True), (0, False)]:
            mdb.users.update_one(uid, {"$set": {"pages_used": used}})
            me = demo.get(f"{API}/auth/me").json()
            assert me["low_page_alert"] is expected, (used, me)
            assert me["usage_pages"] == used
        # paid plan monthly
        mdb.users.update_one(uid, {"$set": {"plan": "starter", "usage_period": __import__("datetime").datetime.utcnow().strftime("%Y-%m"), "period_pages": 160}})
        me = demo.get(f"{API}/auth/me").json()
        assert me["page_limit"] == 200 and me["low_page_alert"] is True and me["limit_period"] == "month"
        mdb.users.update_one(uid, {"$set": {"period_pages": 159}})
        assert demo.get(f"{API}/auth/me").json()["low_page_alert"] is False
    finally:
        mdb.users.update_one(uid, {"$set": {"pages_used": 0, "plan": "free"}, "$unset": {"usage_period": "", "period_pages": ""}})


def test_login_bad_password_401():
    r = requests.post(f"{API}/auth/login", json={"email": f"TEST_nobody_{uuid.uuid4().hex[:6]}@x.com", "password": "wrong"})
    assert r.status_code == 401


def test_register_refresh_logout():
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    try:
        r = s.post(f"{API}/auth/register", json={"name": "TEST_User", "email": email, "password": "Passw0rd!x"})
        assert r.status_code == 200 and r.json()["email"] == email and r.json()["low_page_alert"] is False
        s.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        assert mdb.users.find_one({"email": email})["password_hash"].startswith("$2b$")
        assert s.post(f"{API}/auth/register", json={"name": "x", "email": email, "password": "Passw0rd!x"}).status_code == 400
        assert s.post(f"{API}/auth/refresh").status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 200
        assert s.post(f"{API}/auth/logout").status_code == 200
        s.cookies.clear()
        assert s.get(f"{API}/auth/me").status_code == 401
    finally:
        mdb.users.delete_one({"email": email})


# ---------- Clients ----------
def test_clients_crud_and_isolation(demo):
    r = demo.post(f"{API}/clients", json={"name": "  TEST_Client  ", "industry": "Retail", "platforms": ["shopify", "xx"]})
    assert r.status_code == 200
    c = r.json()
    assert c["name"] == "TEST_Client" and c["platforms"] == ["shopify"] and "_id" not in c
    assert any(x["id"] == c["id"] for x in demo.get(f"{API}/clients").json())
    u = demo.put(f"{API}/clients/{c['id']}", json={"name": "TEST_Client2", "platforms": []})
    assert u.status_code == 200 and u.json()["name"] == "TEST_Client2"
    # other user cannot see / modify
    other = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    ro = other.post(f"{API}/auth/register", json={"name": "TEST_Other", "email": email, "password": "Passw0rd!x"})
    other.headers["X-CSRF-Token"] = ro.json()["csrf_token"]
    try:
        assert all(x["id"] != c["id"] for x in other.get(f"{API}/clients").json())
        assert other.put(f"{API}/clients/{c['id']}", json={"name": "hack"}).status_code == 404
        assert other.delete(f"{API}/clients/{c['id']}").status_code == 404
    finally:
        mdb.users.delete_one({"email": email})
    assert demo.delete(f"{API}/clients/{c['id']}").status_code == 200
    assert demo.delete(f"{API}/clients/{c['id']}").status_code == 404


# ---------- Payout splitter ----------
@pytest.mark.parametrize("platform", ["toast", "doordash", "ubereats", "shopify", "stripe", "lawpay"])
def test_payout_each_platform(demo, demo_client, platform):
    sample = demo.get(f"{API}/payouts/sample/{platform}")
    assert sample.status_code == 200 and "text/csv" in sample.headers["content-type"]
    r = demo.post(f"{API}/payouts", data={"client_id": demo_client["id"], "platform": platform, "commission_rate": "25"},
                  files={"file": (f"{platform}.csv", sample.content, "text/csv")})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["ledger"]["balanced"] is True and p["ledger"]["total_debits"] == p["ledger"]["total_credits"]
    assert p["rows_parsed"] > 0 and p["gross_total"] > 0
    if platform == "lawpay":
        assert p["gross_total"] == 9250.0 and p["fee_total"] == 272.88
        accts = [l["account"] for l in p["ledger"]["lines"]]
        assert "Trust Bank Account (IOLTA)" in accts and "Client Trust Liability" in accts
        rr = demo.post(f"{API}/payouts/{p['id']}/recalculate", json={"commission_rate": 10})
        assert rr.status_code == 400
    else:
        assert p["commission_rate"] == 25.0
        rr = demo.post(f"{API}/payouts/{p['id']}/recalculate", json={"commission_rate": 12.5})
        assert rr.status_code == 200 and rr.json()["commission_rate"] == 12.5 and rr.json()["ledger"]["balanced"]
        assert demo.get(f"{API}/payouts/{p['id']}").json()["commission_rate"] == 12.5
    q = demo.get(f"{API}/payouts/{p['id']}/qbo")
    assert q.status_code == 200 and q.text.startswith("Journal No,Journal Date,Account,Debits,Credits")
    assert "attachment" in q.headers.get("content-disposition", "")


def test_payout_errors(demo, demo_client):
    assert demo.get(f"{API}/payouts/sample/nope").status_code == 404
    r = demo.post(f"{API}/payouts", data={"client_id": demo_client["id"], "platform": "nope"},
                  files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 400
    r = demo.post(f"{API}/payouts", data={"client_id": demo_client["id"], "platform": "lawpay"},
                  files={"file": ("a.csv", b"Date,Amount\n2026-01-01,10\n", "text/csv")})
    assert r.status_code == 400 and "fee column" in r.json()["detail"]
    assert demo.get(f"{API}/payouts/pay_doesnotexist").status_code == 404


# ---------- Statements ----------
def test_statement_engine_and_validation(demo, demo_client):
    e = demo.get(f"{API}/statements/engine").json()
    assert e["engine"] == "aws_textract"
    r = demo.post(f"{API}/statements", data={"client_id": demo_client["id"]}, files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400


def test_statement_textract_failure_not_charged(demo, demo_client):
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0}})
    r = demo.post(f"{API}/statements", data={"client_id": demo_client["id"]},
                  files={"file": ("TEST_stmt.pdf", blank_pdf(1), "application/pdf")}, timeout=90)
    print("statement status", r.status_code, r.text[:300])
    assert r.status_code in (424, 503, 200)
    used = mdb.users.find_one({"email": DEMO["email"]})["pages_used"]
    if r.status_code in (424, 503):
        assert used == 0
        if r.status_code == 424:
            assert "not charged" in r.json()["detail"]
    else:
        assert used == 1
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0}})


def test_statement_page_cap_402(demo, demo_client):
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 4}})
    try:
        r = demo.post(f"{API}/statements", data={"client_id": demo_client["id"]},
                      files={"file": ("TEST_big.pdf", blank_pdf(2), "application/pdf")})
        assert r.status_code == 402 and "Free trial limit" in r.json()["detail"]
        assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == 4
    finally:
        mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0}})


# ---------- History / dashboard / billing ----------
def test_history_dashboard_billing(demo, demo_client):
    h = demo.get(f"{API}/history")
    assert h.status_code == 200 and isinstance(h.json(), list)
    assert all("rows" not in i and "_id" not in i for i in h.json())
    hp = demo.get(f"{API}/history", params={"kind": "payout", "client_id": demo_client["id"]}).json()
    assert len(hp) >= 6 and all(i["kind"] == "payout" for i in hp)
    assert isinstance(demo.get(f"{API}/history", params={"kind": "needs_review"}).json(), list)
    assert isinstance(demo.get(f"{API}/history/review-count").json()["needs_review"], int)
    d = demo.get(f"{API}/dashboard/summary").json()
    assert set(d) >= {"clients", "statements", "payouts", "transactions_extracted"} and d["payouts"] >= 6
    b = demo.get(f"{API}/billing/summary").json()
    assert b["plan"] == "free" and "low_page_alert" in b and b["has_portal"] is False
    # delete history
    pid = hp[0]["id"]
    assert demo.delete(f"{API}/history/payout/{pid}").status_code == 200
    assert demo.get(f"{API}/payouts/{pid}").status_code == 404
    assert demo.delete(f"{API}/history/bogus/x").status_code == 404


def test_checkout_and_portal(demo):
    r = demo.post(f"{API}/payments/checkout", json={"plan": "starter", "origin_url": BASE_URL}, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("https://checkout.stripe.com")
    sid = r.json()["session_id"]
    assert requests.get(f"{API}/payments/status/{sid}").status_code == 401
    st = demo.get(f"{API}/payments/status/{sid}").json()
    assert st["payment_status"] in ("pending", "unpaid") and st["plan"] == "starter"
    assert demo.post(f"{API}/payments/checkout", json={"plan": "gold", "origin_url": BASE_URL}).status_code == 400
    assert demo.post(f"{API}/billing/portal", json={"origin_url": BASE_URL}).status_code == 400
    mdb.payment_transactions.delete_one({"session_id": sid})


def test_unauth_and_webhooks():
    for path in ["/clients", "/history", "/dashboard/summary", "/billing/summary", "/auth/me"]:
        assert requests.get(f"{API}{path}").status_code == 401
    assert requests.post(f"{API}/webhooks/stripe", data=b"{}", headers={"stripe-signature": "bad"}).status_code == 400
    assert requests.post(f"{API}/webhooks/textract", data=b"{}", headers={"X-LedgerStream-Signature": "bad"}).status_code == 401


def test_contact_validation(demo):
    assert requests.post(f"{API}/contact", json={}).status_code == 401
    assert demo.post(f"{API}/contact", json={"desk": "x", "name": "a", "role": "other", "message": "1234567890"}).status_code == 422
    assert demo.post(f"{API}/contact", json={"desk": "support", "name": "a", "role": "other", "message": "short"}).status_code == 422


def test_cors_preflight():
    r = requests.options(f"{API}/auth/login", headers={"Origin": BASE_URL, "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == BASE_URL
    assert r.headers.get("access-control-allow-credentials") == "true"
