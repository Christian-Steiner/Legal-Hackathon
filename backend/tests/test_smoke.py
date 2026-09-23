"""End-to-end smoke test in mock mode against a temp SQLite DB. Run: uv run pytest"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app import schemas  # noqa: E402
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
        # The whole alert is in the draft's language, which is the client's preferred language
        company = client.get(f"/api/companies/{d['company_id']}").json()
        assert d["language"] == alert["language"] == company["preferred_language"]
        assert alert["disclaimer"] == schemas.DISCLAIMERS[alert["language"]]
        # Approved drafts are frozen
        assert client.put(f"/api/drafts/{d['id']}", json={"summary": "x"}, headers=LAWYER).status_code == 409

        preview = client.get(f"/api/alerts/{alert['id']}/email-preview").json()
        assert preview["to"] and "LEXR" in preview["body_text"]
        assert schemas.DISCLAIMERS[alert["language"]] in preview["body_text"]
        # Per-department email: only that department's address and part
        dep = alert["departments"][0]
        one = client.get(f"/api/alerts/{alert['id']}/email-preview", params={"department_id": dep["department_id"]}).json()
        assert len(one["to"]) == 1 and dep["why"] in one["body_text"]
        for other in alert["departments"][1:]:
            assert other["why"] not in one["body_text"]

        # Revision request regenerates and returns to pending with a new version
        d2 = drafts[1]
        r = client.post(f"/api/drafts/{d2['id']}/request-revision", json={"comment": "shorter"}, headers=LAWYER).json()
        assert r["status"] == "pending" and r["version"] == 2

        actions = {e["action"] for e in client.get("/api/audit", params={"limit": 5000}).json()}
        assert {"ingest.created", "classify", "match", "draft.generated", "draft.edited", "draft.approved",
                "alert.delivered", "draft.revision_requested"} <= actions
