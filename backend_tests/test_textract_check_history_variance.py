# Iteration 9: Textract engine check endpoint (real AWS -> scp_blocked), cooldown, isolation; History kind=variance + review-count
import io
import uuid

import pytest
import requests
from test_ledgerstream_regression import API, DEMO, mdb


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=DEMO)
    if r.status_code != 200:
        pytest.skip("login failed")
    uid = sess.get(f"{API}/auth/me").json()["user_id"]
    mdb.textract_checks.delete_many({"user_id": uid})
    sess.uid = uid
    yield sess
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0, "plan": "free", "subscription_status": "trial"}})


@pytest.fixture(scope="module")
def other():
    sess = requests.Session()
    email = f"test_iso_{uuid.uuid4().hex[:6]}@example.com"
    r = sess.post(f"{API}/auth/register", json={"email": email, "password": "TestPass#2026", "name": "TEST Iso", "firm_name": "TEST Firm"})
    assert r.status_code == 200, r.text
    yield sess
    u = mdb.users.find_one({"email": email})
    if u:
        mdb.textract_checks.delete_many({"user_id": u["user_id"]})
        mdb.clients.delete_many({"owner_id": u["user_id"]})
        mdb.user_sessions.delete_many({"user_id": u["user_id"]})
    mdb.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def client(s):
    c = s.post(f"{API}/clients", json={"name": "TEST_HistVarClient", "platforms": ["toast"]}).json()
    yield c
    s.delete(f"{API}/clients/{c['id']}")
    mdb.payouts.delete_many({"client_id": c["id"]})


# Engine check: scp_blocked with 3 steps, no pages charged, persisted
def test_engine_check_scp(s):
    before = mdb.users.find_one({"email": DEMO["email"]})["pages_used"]
    r = s.post(f"{API}/statements/engine/check", timeout=90)
    print(r.status_code, r.text)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "scp_blocked"
    assert [x["id"] for x in d["steps"]] == ["config", "credentials", "textract"]
    assert [x["ok"] for x in d["steps"]] == [True, True, False]
    assert "checked_at" in d and "user_id" not in d and "_id" not in d
    assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == before
    assert mdb.textract_checks.count_documents({"user_id": s.uid}) == 1


# Cooldown 429
def test_engine_check_cooldown(s):
    r = s.post(f"{API}/statements/engine/check", timeout=30)
    assert r.status_code == 429 and "30 seconds" in r.json()["detail"]
    assert mdb.textract_checks.count_documents({"user_id": s.uid}) == 1


# GET engine returns last_check for owner only
def test_engine_last_check_isolation(s, other):
    d = s.get(f"{API}/statements/engine").json()
    assert d["engine"] == "aws_textract" and d["configured"] is True
    assert d["last_check"]["status"] == "scp_blocked" and "user_id" not in d["last_check"]
    o = other.get(f"{API}/statements/engine").json()
    assert o["last_check"] is None


# Unauth
def test_engine_check_unauth():
    assert requests.post(f"{API}/statements/engine/check").status_code == 401


# History variance filter + review-count
def test_history_variance_and_counts(s, client):
    rc0 = s.get(f"{API}/history/review-count").json()
    assert set(rc0) == {"needs_review", "variance"}
    toast = s.get(f"{API}/payouts/sample/toast").content
    lawpay = s.get(f"{API}/payouts/sample/lawpay").content
    up = lambda p, c: s.post(f"{API}/payouts", data={"client_id": client["id"], "platform": p, "commission_rate": "30"},
                             files={"file": ("f.csv", io.BytesIO(c), "text/csv")}).json()
    t, l = up("toast", toast), up("lawpay", lawpay)
    assert t["net_variance"]["flagged"] is True and l["net_variance"]["flagged"] is False
    v = s.get(f"{API}/history", params={"kind": "variance", "client_id": client["id"]}).json()
    assert [x["id"] for x in v] == [t["id"]]
    assert all(x["kind"] == "payout" and x["net_variance"]["flagged"] for x in s.get(f"{API}/history", params={"kind": "variance"}).json())
    rc1 = s.get(f"{API}/history/review-count").json()
    assert rc1["variance"] == rc0["variance"] + 1 and rc1["needs_review"] == rc0["needs_review"]
    allh = s.get(f"{API}/history", params={"client_id": client["id"]}).json()
    assert {x["id"] for x in allh} == {t["id"], l["id"]}
    # recalc clears the flag -> drops from variance list
    s.post(f"{API}/payouts/{t['id']}/recalculate", json={"commission_rate": 30.5379})
    assert s.get(f"{API}/history", params={"kind": "variance", "client_id": client["id"]}).json() == []
    assert s.get(f"{API}/history/review-count").json()["variance"] == rc0["variance"]
