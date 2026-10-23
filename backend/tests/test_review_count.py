# Review count badge API + history needs_review filter + robots.txt + landing SEO head tests
import os
import uuid
import json
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
DEMO = {"email": "demo@ledgerstream.ai", "password": "LedgerDemo#2026"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def demo():
    return _login(DEMO)


# Review count endpoint
class TestReviewCount:
    def test_demo_count_is_2(self, demo):
        r = demo.get(f"{BASE_URL}/api/history/review-count")
        assert r.status_code == 200
        assert r.json() == {"needs_review": 2}

    def test_unauth_401(self):
        r = requests.get(f"{BASE_URL}/api/history/review-count")
        assert r.status_code == 401

    def test_other_user_zero(self):
        email = f"test_rc_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "TestPass#2026", "name": "TEST RC", "firm_name": "TEST Firm"})
        assert r.status_code in (200, 201), r.text
        tok = r.json().get("access_token") or r.json().get("token")
        if tok:
            s.headers["Authorization"] = f"Bearer {tok}"
        r2 = s.get(f"{BASE_URL}/api/history/review-count")
        assert r2.status_code == 200
        assert r2.json()["needs_review"] == 0
        h = s.get(f"{BASE_URL}/api/history", params={"kind": "needs_review"})
        assert h.status_code == 200 and h.json() == []


# History needs_review filter
class TestHistoryFilter:
    def test_needs_review_list(self, demo):
        r = demo.get(f"{BASE_URL}/api/history", params={"kind": "needs_review"})
        assert r.status_code == 200
        ids = sorted(i["id"] for i in r.json())
        assert ids == ["stm_TESTbad1", "stm_TESTbad2"]
        for i in r.json():
            assert "_id" not in i and "rows" not in i
            assert i["summary"]["reconciliation"]["status"] == "mismatch"

    def test_full_history_includes_ok(self, demo):
        r = demo.get(f"{BASE_URL}/api/history")
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()]
        assert "stm_TESTok" in ids


# Static SEO assets
class TestSEO:
    def test_robots(self):
        r = requests.get(f"{BASE_URL}/robots.txt")
        assert r.status_code == 200
        assert "User-agent" in r.text and "Disallow: /dashboard" in r.text

    def test_index_head(self):
        r = requests.get(f"{BASE_URL}/")
        assert r.status_code == 200
        html = r.text
        assert "<title>LedgerStream AI | The Financial Ingestion Hub for Modern Bookkeepers</title>" in html
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        assert m
        data = json.loads(m.group(1))
        nodes = data.get("@graph", [data])
        data = next(n for n in nodes if n.get("@type") == "SoftwareApplication")
        prices = sorted(float(o["price"]) for o in data["offers"])
        assert prices == [0, 99, 199]
        assert all(o["priceCurrency"] == "USD" for o in data["offers"])
