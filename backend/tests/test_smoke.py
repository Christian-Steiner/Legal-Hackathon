"""End-to-end smoke test in mock mode against a temp SQLite DB. Run: uv run pytest"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from scripts import seed  # noqa: E402

LAWYER = {"X-Role": "lawyer", "X-Actor": "Test Lawyer"}


def test_pipeline_and_approval_gate():
    seed.main()
    with TestClient(app) as client:
        assert client.post("/api/pipeline/run-all").status_code == 403  # lawyer only
        assert client.post("/api/pipeline/run-all", headers=LAWYER).status_code == 200

        drafts = client.get("/api/drafts", params={"status": "pending"}).json()
        assert drafts, "mock pipeline should produce drafts"
        d = drafts[0]
        detail = client.get(f"/api/drafts/{d['id']}").json()
        assert detail["update"]["title"] and detail["match"]["llm_reason"]

        # No alert without approval
        assert client.get(f"/api/companies/{d['company_id']}/alerts").json() == []
        # Client cannot approve
        r = client.post(f"/api/drafts/{d['id']}/approve", json={}, headers={"X-Role": "client", "X-Actor": "x"})
        assert r.status_code == 403

        r = client.put(f"/api/drafts/{d['id']}", json={"summary": "Edited by lawyer."}, headers=LAWYER)
        assert r.status_code == 200 and r.json()["edited_by_lawyer"]

        alert = client.post(f"/api/drafts/{d['id']}/approve", json={"comment": "ok"}, headers=LAWYER).json()
        assert alert["reviewed_by"] == "lawyer:Test Lawyer" and alert["summary"] == "Edited by lawyer."
        assert "not a full legal assessment" in alert["disclaimer"]
        # Approved drafts are frozen
        assert client.put(f"/api/drafts/{d['id']}", json={"summary": "x"}, headers=LAWYER).status_code == 409

        preview = client.get(f"/api/alerts/{alert['id']}/email-preview").json()
        assert preview["to"] and "Reviewed by LEXR" in preview["body_text"]

        # Revision request regenerates and returns to pending with a new version
        d2 = drafts[1]
        r = client.post(f"/api/drafts/{d2['id']}/request-revision", json={"comment": "shorter"}, headers=LAWYER).json()
        assert r["status"] == "pending" and r["version"] == 2

        actions = {e["action"] for e in client.get("/api/audit", params={"limit": 5000}).json()}
        assert {"ingest.created", "classify", "match", "draft.generated", "draft.edited", "draft.approved",
                "alert.delivered", "draft.revision_requested"} <= actions
