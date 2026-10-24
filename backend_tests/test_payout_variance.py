# Iteration 8: Payout Variance Note (net_variance) + Textract SCP 424 message
import io
import pytest
import requests
from test_ledgerstream_regression import API, DEMO, mdb, blank_pdf


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=DEMO)
    if r.status_code != 200:
        pytest.skip("login failed")
    yield sess
    mdb.users.update_one({"email": DEMO["email"]}, {"$set": {"pages_used": 0, "plan": "free", "subscription_status": "trial"}})


@pytest.fixture(scope="module")
def client(s):
    c = s.post(f"{API}/clients", json={"name": "TEST_VarianceClient", "platforms": ["toast"]}).json()
    yield c
    s.delete(f"{API}/clients/{c['id']}")
    mdb.payouts.delete_many({"client_id": c["id"]})
    mdb.statements.delete_many({"client_id": c["id"]})


def upload(s, client, platform, content, rate=30.0, name="f.csv"):
    return s.post(f"{API}/payouts", data={"client_id": client["id"], "platform": platform, "commission_rate": str(rate)},
                  files={"file": (name, io.BytesIO(content), "text/csv")})


def sample(s, platform):
    r = s.get(f"{API}/payouts/sample/{platform}")
    assert r.status_code == 200
    return r.content


# Toast sample @30% is flagged with exact numbers
def test_toast_flagged(s, client):
    r = upload(s, client, "toast", sample(s, "toast"), 30)
    assert r.status_code == 200, r.text
    v = r.json()["net_variance"]
    assert v == {"file_net": 5919.87, "calculated_net": 5965.71, "difference": -45.84, "flagged": True}
    assert v["calculated_net"] == r.json()["ledger"]["lines"][0]["debit"]
    pytest.toast_id = r.json()["id"]


# Recalculate updates variance; a matching rate clears flag; persisted
def test_recalc_updates_variance(s, client):
    pid = pytest.toast_id
    r = s.post(f"{API}/payouts/{pid}/recalculate", json={"commission_rate": 20})
    v = r.json()["net_variance"]
    assert r.status_code == 200 and v["calculated_net"] == r.json()["ledger"]["lines"][0]["debit"]
    assert v["flagged"] is True and v["difference"] == round(5919.87 - v["calculated_net"], 2)
    r = s.post(f"{API}/payouts/{pid}/recalculate", json={"commission_rate": 30.5379})
    v = r.json()["net_variance"]
    assert v["calculated_net"] == 5919.87 and v["difference"] == 0 and v["flagged"] is False, v
    g = s.get(f"{API}/payouts/{pid}").json()
    assert g["net_variance"]["flagged"] is False and g["commission_rate"] == 30.5379


# LawPay sample: trust deposit == gross == file net -> not flagged
def test_lawpay_match(s, client):
    r = upload(s, client, "lawpay", sample(s, "lawpay"))
    assert r.status_code == 200, r.text
    d = r.json()
    print(d["net_variance"], d["gross_total"], d["file_net_total"])
    assert d["net_variance"] is not None and d["net_variance"]["flagged"] is False


# No net column -> null
def test_no_net_column_null(s, client):
    csv = b"Date,Gross Sales\n2026-01-01,100.00\n2026-01-02,250.50\n"
    r = upload(s, client, "toast", csv, 25)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["net_column"] is None and d["file_net_total"] is None and d["net_variance"] is None
    r2 = s.post(f"{API}/payouts/{d['id']}/recalculate", json={"commission_rate": 10})
    assert r2.json()["net_variance"] is None


# Other platforms' samples produce a net_variance dict or null consistently
@pytest.mark.parametrize("platform", ["doordash", "ubereats", "shopify", "stripe"])
def test_other_platforms(s, client, platform):
    r = upload(s, client, platform, sample(s, platform))
    assert r.status_code == 200
    d = r.json()
    v = d["net_variance"]
    print(platform, v)
    if d["file_net_total"] is None:
        assert v is None
    else:
        assert round(v["file_net"] - v["calculated_net"], 2) == v["difference"]
        assert v["flagged"] == (v["difference"] != 0)


# Textract SCP 424 message, not charged
def test_textract_scp_424(s, client):
    before = mdb.users.find_one({"email": DEMO["email"]})["pages_used"]
    r = s.post(f"{API}/statements", data={"client_id": client["id"]},
               files={"file": ("TEST_s.pdf", io.BytesIO(blank_pdf(1)), "application/pdf")}, timeout=90)
    print(r.status_code, r.text)
    assert r.status_code == 424
    det = r.json()["detail"]
    assert "service control policy" in det and "not charged" in det
    assert mdb.users.find_one({"email": DEMO["email"]})["pages_used"] == before
