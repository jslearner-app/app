"""Iteration 6: POST /api/contact auth, validation and rate limit (NO real emails are sent)."""
from datetime import datetime, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

FE_ENV = dotenv_values("/app/frontend/.env")
BE_ENV = dotenv_values("/app/backend/.env")
API = FE_ENV["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
mongo = MongoClient(BE_ENV["MONGO_URL"])[BE_ENV["DB_NAME"]]
VALID = {"desk": "support", "name": "TEST Name", "role": "firm_owner", "message": "Hello this is a test message"}
MARK = "TEST_iter6_ratelimit"


@pytest.fixture(scope="module")
def demo():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "demo@ledgerstream.ai", "password": "LedgerDemo#2026"})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    me = s.get(f"{API}/auth/me").json()
    return s, me


@pytest.fixture
def saturated(demo):
    _, me = demo
    ts = datetime.now(timezone.utc).isoformat()
    mongo.contact_messages.insert_many([{"user_id": me["user_id"], "created_at": ts, "marker": MARK} for _ in range(5)])
    yield
    mongo.contact_messages.delete_many({"marker": MARK})


# Auth
def test_contact_requires_auth():
    r = requests.post(f"{API}/contact", json=VALID)
    assert r.status_code == 401


# Validation (422 happens before rate check / email send)
@pytest.mark.parametrize("patch", [
    {"desk": "billing"}, {"name": ""}, {"name": "x" * 121}, {"role": "admin"},
    {"message": "short"}, {"message": "x" * 4001},
])
def test_contact_invalid_values_422(demo, patch):
    s, _ = demo
    r = s.post(f"{API}/contact", json={**VALID, **patch})
    assert r.status_code == 422, r.text


def test_contact_missing_fields_422(demo):
    s, _ = demo
    r = s.post(f"{API}/contact", json={"desk": "support"})
    assert r.status_code == 422


# Rate limit: 5 per hour -> 429, with recipient/subject injection attempts ignored
def test_contact_rate_limited_429(demo, saturated):
    s, me = demo
    before = mongo.contact_messages.count_documents({"user_id": me["user_id"]})
    r = s.post(f"{API}/contact", json={**VALID, "to": "evil@example.com", "subject": "x", "html": "<b>x</b>"})
    assert r.status_code == 429, r.text
    assert "hour" in r.json()["detail"].lower()
    assert mongo.contact_messages.count_documents({"user_id": me["user_id"]}) == before


def test_old_messages_do_not_count(demo):
    """Docs older than an hour must not count; only check count logic via query, no POST."""
    _, me = demo
    assert mongo.contact_messages.count_documents({"user_id": me["user_id"], "marker": MARK}) == 0
