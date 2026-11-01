# Iteration 12: live Google Document AI (Form Parser, eu) - engine check ready, real table upload, 15-page cap, history, delete; Google OAuth 401
import io

import pytest
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from test_ledgerstream_regression import API, BASE_URL, DEMO, blank_pdf, mdb

HEADER = ["Date", "Description", "Reference", "Withdrawals", "Deposits", "Balance"]
ROWS = [
    ["09/01/2026", "Opening deposit", "", "", "1,000.00", "1,000.00"],
    ["09/02/2026", "Office supplies", "1001", "150.25", "", "849.75"],
    ["09/03/2026", "Client payment", "", "", "420.00", "1,269.75"],
]


def sample_pdf() -> bytes:
    buf = io.BytesIO()
    t = Table([HEADER, *ROWS])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buf, pagesize=letter).build([Paragraph("TEST Bank Statement", getSampleStyleSheet()["Title"]), t])
    return buf.getvalue()


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=DEMO)
    if r.status_code != 200:
        pytest.skip("login failed")
    sess.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    sess.uid = sess.get(f"{API}/auth/me").json()["user_id"]
    mdb.engine_checks.delete_many({"user_id": sess.uid})
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0}})
    yield sess
    mdb.engine_checks.delete_many({"user_id": sess.uid})
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0, "plan": "free", "subscription_status": "trial"}})


@pytest.fixture(scope="module")
def burger(s):
    cs = s.get(f"{API}/clients").json()
    return next(c for c in cs if c["name"] == "The Burger Shack")


# Engine check: ready with 4 ok steps, no pages charged
def test_engine_check_ready(s):
    r = s.post(f"{API}/statements/engine/check", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ready"
    assert [x["id"] for x in d["steps"]] == ["config", "credentials", "processing", "pipeline"]
    assert all(x["ok"] for x in d["steps"])
    assert "3 transaction" in d["steps"][3]["detail"]
    assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == 0
    e = s.get(f"{API}/statements/engine").json()
    assert e["configured"] is True and e["region"] == "eu" and e["last_check"]["status"] == "ready"
    assert s.post(f"{API}/statements/engine/check").status_code == 429


# Real upload: 3 rows exact amounts, reconciled, 1 page charged, history, export, edit -> mismatch, delete
def test_real_upload_flow(s, burger):
    r = s.post(f"{API}/statements", data={"client_id": burger["id"]},
               files={"file": ("TEST_live.pdf", io.BytesIO(sample_pdf()), "application/pdf")}, timeout=150)
    assert r.status_code == 200, r.text
    d = r.json()
    try:
        assert d["engine"] == "google_document_ai" and d["pages"] == 1
        assert "statement_totals" in d and set(d["statement_totals"]) == {"starting_balance", "ending_balance"}
        rows = d["rows"]
        print(rows)
        assert len(rows) == 3
        assert [r_["date"] for r_ in rows] == ["09/01/2026", "09/02/2026", "09/03/2026"]
        assert [r_["description"] for r_ in rows] == ["Opening deposit", "Office supplies", "Client payment"]
        assert [r_["deposit"] for r_ in rows] == [1000.0, None, 420.0]
        assert [r_["withdrawal"] for r_ in rows] == [None, 150.25, None]
        assert [r_["balance"] for r_ in rows] == [1000.0, 849.75, 1269.75]
        assert rows[1]["reference"] == "1001"
        assert d["summary"]["reconciliation"]["status"] == "reconciled"
        assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == 1
        h = s.get(f"{API}/history").json()
        assert any(x["id"] == d["id"] and x["kind"] == "statement" for x in h)
        csv = s.get(f"{API}/statements/{d['id']}/export", params={"fmt": "csv"})
        assert csv.status_code == 200 and b"Office supplies" in csv.content and b"150.25" in csv.content
        x = s.get(f"{API}/statements/{d['id']}/export", params={"fmt": "xlsx"})
        assert x.status_code == 200 and x.content[:2] == b"PK"
        rows[1]["balance"] = 800.00
        u = s.put(f"{API}/statements/{d['id']}/rows", json={"rows": rows})
        assert u.status_code == 200 and u.json()["summary"]["reconciliation"]["status"] == "mismatch"
        assert s.get(f"{API}/statements/{d['id']}").json()["rows"][1]["balance"] == 800.0
    finally:
        dl = s.delete(f"{API}/history/statement/{d['id']}")
        assert dl.status_code in (200, 204)
        assert s.get(f"{API}/statements/{d['id']}").status_code == 404


# 16-page PDF rejected with 15-page message, no pages charged
def test_16_pages_rejected(s, burger):
    before = mdb.users.find_one({"email": DEMO["email"]})["pages_used"]
    r = s.post(f"{API}/statements", data={"client_id": burger["id"]},
               files={"file": ("TEST_16.pdf", io.BytesIO(blank_pdf(16)), "application/pdf")})
    assert r.status_code == 400 and "up to 15 pages" in r.json()["detail"] and "16" in r.json()["detail"]
    assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == before


# Google OAuth: fake code -> 401 now that keys are present; untrusted redirect -> 400/403
def test_google_fake_code_401():
    mdb.rate_limits.delete_many({})
    r = requests.post(f"{API}/auth/google", json={"code": "fake-code-123", "redirect_uri": f"{BASE_URL}/auth/google"})
    assert r.status_code == 401 and r.json()["detail"].startswith("Google sign-in failed")
    r = requests.post(f"{API}/auth/google", json={"code": "x", "redirect_uri": "https://evil.example.com/auth/google"})
    assert r.status_code in (400, 403)
    r = requests.post(f"{API}/auth/google", json={"code": "x", "redirect_uri": f"{BASE_URL}/other"})
    assert r.status_code == 400
