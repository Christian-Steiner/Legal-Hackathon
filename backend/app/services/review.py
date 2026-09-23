"""Human-in-the-loop review. THE ONLY PLACE an Alert is created (backend-enforced approval gate)."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, schemas
from app.models import Alert, Draft
from app.services import pipeline


def warnings_for(d: Draft) -> list[str]:
    """Quality flags shown prominently on the review screen."""
    w = []
    if not d.citations:
        w.append("NO_CITATIONS: this draft cites no source - do not approve without adding one.")
    elif any(not (c.get("eli") or c.get("source_url")) for c in d.citations):
        w.append("CITATION_WITHOUT_SOURCE: at least one citation has no ELI / source link.")
    if any(not c.get("article") for c in d.citations):
        w.append("CITATION_WITHOUT_ARTICLE: at least one citation has no article reference.")
    if d.update and d.update.is_simulated:
        w.append("SIMULATED_SOURCE: based on the organisers' simulated dataset, not an official publication.")
    if d.model_version.startswith("mock"):
        w.append("TEMPLATE_DRAFT: generated without an LLM (mock mode).")
    if not d.affected_departments:
        w.append("NO_DEPARTMENTS: no department routed.")
    # TODO(ws2): flag claims whose quote is not found in update.source_text
    return w


def _get(db: Session, draft_id: int) -> Draft:
    d = db.get(Draft, draft_id)
    if not d:
        raise HTTPException(404, "Draft not found")
    return d


def _require_open(d: Draft) -> None:
    if d.status == "approved":
        raise HTTPException(409, "Draft is already approved and delivered; it can no longer be changed.")


def edit(db: Session, draft_id: int, patch: schemas.DraftEdit, lawyer: str) -> Draft:
    d = _get(db, draft_id)
    _require_open(d)
    changes = patch.model_dump(exclude_none=True, mode="json")
    before = {k: getattr(d, k) for k in changes}
    for k, v in changes.items():
        setattr(d, k, v)
    d.edited_by_lawyer = True
    d.version += 1
    snapshot = {k: getattr(d, k) for k in ("summary", "affected_departments", "next_steps", "urgency", "citations")}
    d.revision_history = [*d.revision_history, {"version": d.version, "at": _now(), "by": lawyer, "change": "edited",
                                                "snapshot": snapshot}]
    audit.log(db, actor=lawyer, action="draft.edited", object_type="draft", object_id=d.id,
              details={"fields": list(changes), "before": before, "after": changes})
    db.commit()
    return d


def approve(db: Session, draft_id: int, lawyer: str, comment: str = "") -> Alert:
    d = _get(db, draft_id)
    _require_open(d)
    if d.status != "pending":
        raise HTTPException(409, f"Only pending drafts can be approved (status is {d.status}).")
    if not d.citations:
        raise HTTPException(422, "Cannot approve a draft without citations.")
    d.status = "approved"
    d.reviewed_by = lawyer
    d.reviewed_at = datetime.now(timezone.utc)
    d.reviewer_comments = [*d.reviewer_comments, {"at": _now(), "by": lawyer, "decision": "approved", "comment": comment}]
    alert = _create_alert(db, d)
    audit.log(db, actor=lawyer, action="draft.approved", object_type="draft", object_id=d.id,
              details={"version": d.version, "comment": comment, "alert_id": alert.id})
    db.commit()
    return alert


def reject(db: Session, draft_id: int, lawyer: str, comment: str) -> Draft:
    d = _get(db, draft_id)
    _require_open(d)
    d.status = "rejected"
    d.reviewed_by, d.reviewed_at = lawyer, datetime.now(timezone.utc)
    d.reviewer_comments = [*d.reviewer_comments, {"at": _now(), "by": lawyer, "decision": "rejected", "comment": comment}]
    audit.log(db, actor=lawyer, action="draft.rejected", object_type="draft", object_id=d.id, details={"comment": comment})
    db.commit()
    return d


def request_revision(db: Session, draft_id: int, lawyer: str, comment: str) -> Draft:
    """Records the request, then immediately regenerates the draft (step 4) with the comment."""
    d = _get(db, draft_id)
    _require_open(d)
    d.status = "revision_requested"
    d.reviewer_comments = [*d.reviewer_comments, {"at": _now(), "by": lawyer, "decision": "revision_requested",
                                                  "comment": comment}]
    audit.log(db, actor=lawyer, action="draft.revision_requested", object_type="draft", object_id=d.id,
              details={"comment": comment})
    db.commit()
    try:
        pipeline.draft_for_match(db, d.match, revision_comment=comment,
                                 actor_note="regenerated_after_revision_request")
        db.commit()
    except Exception as e:  # keep status revision_requested so the lawyer sees it failed
        db.rollback()
        raise HTTPException(502, f"Regeneration failed: {e}") from e
    return d


def _create_alert(db: Session, d: Draft) -> Alert:
    # Backend gate: refuse unless the draft is approved by a named lawyer. Do not bypass.
    if d.status != "approved" or not d.reviewed_by:
        raise RuntimeError("Alerts can only be created from lawyer-approved drafts.")
    if db.scalar(select(Alert).where(Alert.draft_id == d.id)):
        raise HTTPException(409, "Alert already exists")
    alert = Alert(draft_id=d.id, company_id=d.company_id, departments=d.affected_departments, reviewed_by=d.reviewed_by)
    db.add(alert)
    db.flush()
    audit.log(db, actor="system", action="alert.delivered", object_type="alert", object_id=alert.id,
              details={"draft_id": d.id, "company_id": d.company_id,
                       "departments": [x["name"] for x in d.affected_departments]})
    return alert


def alert_out(a: Alert) -> schemas.AlertOut:
    d = a.draft
    return schemas.AlertOut(
        id=a.id, draft_id=a.draft_id, company_id=a.company_id, departments=a.departments, delivered_at=a.delivered_at,
        reviewed_by=a.reviewed_by, read_at=a.read_at, title=d.update.title, summary=d.summary, next_steps=d.next_steps,
        urgency=d.urgency, citations=d.citations, source_url=d.update.source_url, is_simulated=d.update.is_simulated,
    )


def email_preview(a: Alert) -> schemas.EmailPreview:
    d = a.draft
    emails = {dep.id: dep.contact_email for dep in d.company.departments}
    to = [emails[x["department_id"]] for x in a.departments if x.get("department_id") in emails]
    steps = "\n".join(f"  - {s['action']}" + (f" ({s['department']})" if s.get("department") else "")
                      + (f", by {s['due']}" if s.get("due") else "") for s in d.next_steps)
    cites = "\n".join(f"  [{i + 1}] {c.get('article') or ''} {c.get('eli') or c.get('source_url') or ''}"
                      for i, c in enumerate(d.citations))
    body = (f"{d.update.title}\nUrgency: {d.urgency}\n\n{d.summary}\n\nSuggested next steps:\n{steps}\n\n"
            f"Sources:\n{cites}\n\nReviewed by LEXR ({a.reviewed_by}) on {a.delivered_at:%d.%m.%Y}.\n\n"
            f"{schemas.DISCLAIMER}")
    return schemas.EmailPreview(to=to, subject=f"[LEXR Regulatory Alert] {d.update.title[:90]}", body_text=body)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
