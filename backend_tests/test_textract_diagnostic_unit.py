# Iteration 9: Unit tests for run_textract_diagnostic READY path (faked Textract/STS) and _textract_failure classification
import os
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
os.environ["DATABASE_URL"] = os.environ["MONGO_URL"]
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "AKIATESTFAKE")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "fakesecret")
sys.path.insert(0, str(Path("/app/api")))

import lambda_function as lf  # noqa: E402


def fake_blocks(header, rows):
    """Build realistic Textract PAGE/TABLE/CELL/WORD blocks for a grid."""
    blocks, cell_ids, n = [], [], [0]

    def nid(prefix):
        n[0] += 1
        return f"{prefix}-{n[0]}"

    for r, row in enumerate([header, *rows], start=1):
        for c, text in enumerate(row, start=1):
            cid = nid("cell")
            word_ids = []
            for w in str(text).split():
                wid = nid("word")
                word_ids.append(wid)
                blocks.append({"BlockType": "WORD", "Id": wid, "Text": w, "Confidence": 99.1})
            cell = {"BlockType": "CELL", "Id": cid, "RowIndex": r, "ColumnIndex": c, "RowSpan": 1, "ColumnSpan": 1}
            if word_ids:
                cell["Relationships"] = [{"Type": "CHILD", "Ids": word_ids}]
            blocks.append(cell)
            cell_ids.append(cid)
    table = {"BlockType": "TABLE", "Id": nid("table"), "Relationships": [{"Type": "CHILD", "Ids": cell_ids}]}
    page = {"BlockType": "PAGE", "Id": nid("page"), "Relationships": [{"Type": "CHILD", "Ids": [table["Id"]]}]}
    return [page, table, *blocks]


class FakeTextract:
    def __init__(self, blocks=None, error=None):
        self.blocks, self.error, self.calls = blocks, error, []

    def analyze_document(self, Document, FeatureTypes):
        self.calls.append((Document, FeatureTypes))
        if self.error:
            raise self.error
        return {"Blocks": self.blocks}


class FakeSTS:
    def get_caller_identity(self):
        return {"Arn": "arn:aws:iam::123456789012:user/LedgerStream_Engine"}


def _patch(monkeypatch, textract):
    monkeypatch.setattr(lf, "textract_enabled", lambda: True)
    monkeypatch.setattr(lf, "textract_client", lambda: textract)
    real = lf.boto3.client
    monkeypatch.setattr(lf.boto3, "client", lambda svc, *a, **k: FakeSTS() if svc == "sts" else real(svc, *a, **k))


def ce(code, msg):
    return ClientError({"Error": {"Code": code, "Message": msg}}, "AnalyzeDocument")


# Sample PDF is a valid 1-page PDF
def test_sample_pdf_valid():
    pdf = lf.build_sample_statement_pdf()
    assert pdf.startswith(b"%PDF") and lf.count_pages(pdf) == 1


# READY: all 4 steps ok when Textract returns the sample's table
def test_diagnostic_ready(monkeypatch):
    fake = FakeTextract(blocks=fake_blocks(lf.DIAG_HEADER, lf.DIAG_ROWS))
    _patch(monkeypatch, fake)
    res = lf.run_textract_diagnostic()
    print(res)
    assert res["status"] == "ready"
    assert [s["id"] for s in res["steps"]] == ["config", "credentials", "textract", "pipeline"]
    assert all(s["ok"] for s in res["steps"])
    assert "LedgerStream_Engine" in res["steps"][1]["detail"]
    assert "3 of 3" in res["steps"][3]["detail"] and "reconciled" in res["steps"][3]["detail"]
    doc, feats = fake.calls[0]
    assert doc["Bytes"].startswith(b"%PDF") and feats == ["TABLES"]


# Parse mismatch when Textract drops a row
def test_diagnostic_parse_mismatch(monkeypatch):
    _patch(monkeypatch, FakeTextract(blocks=fake_blocks(lf.DIAG_HEADER, lf.DIAG_ROWS[:2])))
    res = lf.run_textract_diagnostic()
    assert res["status"] == "parse_mismatch" and res["steps"][3]["ok"] is False


# SCP-blocked flow through diagnostic
def test_diagnostic_scp(monkeypatch):
    msg = ("User: arn:aws:iam::1:user/x is not authorized to perform: textract:AnalyzeDocument with an explicit deny "
           "in a service control policy")
    _patch(monkeypatch, FakeTextract(error=ce("AccessDeniedException", msg)))
    res = lf.run_textract_diagnostic()
    assert res["status"] == "scp_blocked" and len(res["steps"]) == 3 and res["steps"][2]["ok"] is False


# Not configured short-circuits
def test_diagnostic_not_configured(monkeypatch):
    monkeypatch.setattr(lf, "textract_enabled", lambda: False)
    res = lf.run_textract_diagnostic()
    assert res["status"] == "not_configured" and len(res["steps"]) == 1


# _textract_failure classification
@pytest.mark.parametrize("code,msg,expected", [
    ("AccessDeniedException", "explicit deny in a service control policy", "scp_blocked"),
    ("AccessDeniedException", "User is not authorized to perform: textract:AnalyzeDocument", "iam_denied"),
    ("UnrecognizedClientException", "The security token included in the request is invalid.", "invalid_keys"),
    ("InvalidSignatureException", "Signature mismatch", "invalid_keys"),
    ("SubscriptionRequiredException", "needs subscription", "not_subscribed"),
    ("ThrottlingException", "Rate exceeded", "textract_error"),
])
def test_failure_classification(code, msg, expected):
    status, detail = lf._textract_failure(ce(code, msg))
    assert status == expected and detail
