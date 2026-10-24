# Iteration 10: CSRF with Google (session_token cookie) sessions
import uuid
from datetime import datetime, timedelta, timezone

import requests
from test_ledgerstream_regression import API, BASE_URL, mdb


def test_google_session_bad_id_401():
    assert requests.post(f"{API}/auth/google/session", json={"session_id": "bogus"}).status_code == 401


def test_session_token_cookie_csrf():
    uid, tok = f"user_test{uuid.uuid4().hex[:8]}", f"TEST_sess_{uuid.uuid4().hex}"
    mdb.users.insert_one({"user_id": uid, "email": f"{uid}@example.com", "name": "TEST G", "auth_provider": "google",
                          "plan": "free", "subscription_status": "trial", "pages_used": 0,
                          "created_at": datetime.now(timezone.utc)})
    mdb.user_sessions.insert_one({"user_id": uid, "session_token": tok, "created_at": datetime.now(timezone.utc),
                                  "expires_at": datetime.now(timezone.utc) + timedelta(days=1)})
    s = requests.Session()
    s.cookies.set("session_token", tok, domain=BASE_URL.split("://")[1])
    try:
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["csrf_token"]
        assert s.post(f"{API}/clients", json={"name": "TEST_g"}).status_code == 403
        r = s.post(f"{API}/clients", json={"name": "TEST_g"}, headers={"X-CSRF-Token": me.json()["csrf_token"]})
        assert r.status_code == 200
        assert s.post(f"{API}/auth/logout").status_code == 200
        assert mdb.user_sessions.find_one({"session_token": tok}) is None
    finally:
        mdb.clients.delete_many({"owner_id": uid})
        mdb.user_sessions.delete_many({"user_id": uid})
        mdb.users.delete_one({"user_id": uid})
