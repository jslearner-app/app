# Iteration 11: own Google OAuth (/api/auth/google), removed Emergent/Textract endpoints, CORS for ledgerstreamai.com, health
import requests
from test_ledgerstream_regression import API, BASE_URL, mdb


def _google(redirect_uri, code="fake_code"):
    return requests.post(f"{API}/auth/google", json={"code": code, "redirect_uri": redirect_uri}, timeout=30)


# Health reports the parser as configured (real Document AI keys set)
def test_health_parser_configured():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "parser_configured": True}


# Untrusted origin in redirect_uri -> 400
def test_google_untrusted_origin():
    r = _google("https://evil.example/auth/google")
    assert r.status_code == 400 and r.json()["detail"] == "Unrecognised app address"


# Wrong path -> 400
def test_google_wrong_path():
    for uri in (f"{BASE_URL}/x", f"{BASE_URL}/auth/google/../x", f"{BASE_URL}/"):
        r = _google(uri)
        assert r.status_code == 400, (uri, r.text)


# http:// variant of a trusted host is rejected
def test_google_http_scheme_rejected():
    r = _google(BASE_URL.replace("https://", "http://") + "/auth/google")
    assert r.status_code == 400


# Validation: missing fields -> 422
def test_google_validation():
    assert requests.post(f"{API}/auth/google", json={"code": "x"}).status_code == 422
    assert requests.post(f"{API}/auth/google", json={"code": "", "redirect_uri": f"{BASE_URL}/auth/google"}).status_code == 422


# Trusted origin + fake code: Google rejects the code -> 401 (own OAuth keys are set)
def test_google_trusted_fake_code():
    r = _google(f"{BASE_URL}/auth/google")
    print("google trusted fake code:", r.status_code, r.text[:200])
    assert r.status_code == 401 and "Google sign-in failed" in r.json()["detail"]


# Old Emergent and Textract endpoints are gone
def test_removed_endpoints():
    assert requests.post(f"{API}/auth/google/session", json={"session_id": "x"}).status_code in (404, 405)
    assert requests.post(f"{API}/webhooks/textract", data=b"{}").status_code in (404, 405)


# CORS: ledgerstreamai.com allowed, preview allowed, evil blocked
def test_cors_origins():
    for origin in ("https://ledgerstreamai.com", BASE_URL):
        r = requests.options(f"{API}/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                            "Access-Control-Request-Headers": "x-csrf-token,content-type"})
        assert r.status_code == 200 and r.headers.get("access-control-allow-origin") == origin
        assert r.headers.get("access-control-allow-credentials") == "true"
        g = requests.get(f"{API}/health", headers={"Origin": origin})
        assert g.headers.get("access-control-allow-origin") == origin
    r = requests.options(f"{API}/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") is None
    g = requests.get(f"{API}/health", headers={"Origin": "https://evil.example"})
    assert g.headers.get("access-control-allow-origin") is None


def teardown_module():
    mdb.rate_limits.delete_many({"key": {"$regex": "^google:"}})
