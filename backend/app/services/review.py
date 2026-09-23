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
    snapshot = {k: getattr(d, k) for k in ("title", "summary", "affected_departments", "next_steps", "urgency", "citations")}
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


def _language(d: Draft) -> str:
    """Language the client sees: the one the draft was written in (older drafts: the client's preference)."""
    lang = d.language or d.company.preferred_language
    return lang if lang in schemas.DISCLAIMERS else "EN"


def alert_out(a: Alert) -> schemas.AlertOut:
    d = a.draft
    lang = _language(d)
    return schemas.AlertOut(
        id=a.id, draft_id=a.draft_id, company_id=a.company_id, departments=a.departments, delivered_at=a.delivered_at,
        reviewed_by=a.reviewed_by, read_at=a.read_at, title=d.title or d.update.title, summary=d.summary,
        next_steps=d.next_steps, urgency=d.urgency, citations=d.citations, source_url=d.update.source_url,
        is_simulated=d.update.is_simulated, language=lang, disclaimer=schemas.DISCLAIMERS[lang],
    )


# Fixed email wording per client language, so the whole notification is in one language.
EMAIL_TEXT = {
    "EN": {"subject": "LEXR regulatory alert", "for": "For", "urgency": "Urgency",
           "urgencies": {"high": "high", "medium": "medium", "low": "low"},
           "why": "Why this concerns you", "steps": "Suggested next steps", "by": "by", "sources": "Sources",
           "reviewed": "Reviewed by LEXR ({who}) on {date}."},
    "DE": {"subject": "LEXR Regulierungs-Update", "for": "Für", "urgency": "Dringlichkeit",
           "urgencies": {"high": "hoch", "medium": "mittel", "low": "niedrig"},
           "why": "Warum Sie das betrifft", "steps": "Empfohlene nächste Schritte", "by": "bis", "sources": "Quellen",
           "reviewed": "Geprüft von LEXR ({who}) am {date}."},
    "FR": {"subject": "Alerte réglementaire LEXR", "for": "Pour", "urgency": "Urgence",
           "urgencies": {"high": "élevée", "medium": "moyenne", "low": "faible"},
           "why": "Pourquoi cela vous concerne", "steps": "Prochaines étapes suggérées", "by": "d'ici le",
           "sources": "Sources", "reviewed": "Vérifié par LEXR ({who}) le {date}."},
    "IT": {"subject": "Avviso normativo LEXR", "for": "Per", "urgency": "Urgenza",
           "urgencies": {"high": "alta", "medium": "media", "low": "bassa"},
           "why": "Perché vi riguarda", "steps": "Prossimi passi suggeriti", "by": "entro il", "sources": "Fonti",
           "reviewed": "Verificato da LEXR ({who}) il {date}."},
}


def email_preview(a: Alert, department_id: int | None = None) -> schemas.EmailPreview:
    """The alert email in the draft's language. With department_id: only that department's part,
    sent only to that department (each department gets what concerns it)."""
    d = a.draft
    lang = _language(d)
    t = EMAIL_TEXT[lang]
    emails = {dep.id: dep.contact_email for dep in d.company.departments}
    deps = [x for x in a.departments if department_id is None or x.get("department_id") == department_id]
    if not deps:
        raise HTTPException(404, "This alert was not routed to that department.")
    names, all_names = {x["name"] for x in deps}, {x["name"] for x in a.departments}
    # Steps for this department, plus steps not assigned to any routed department (so none get lost).
    steps_for = [s for s in d.next_steps
                 if department_id is None or s.get("department") in names or s.get("department") not in all_names]
    to = [emails[x["department_id"]] for x in deps if x.get("department_id") in emails]
    title = d.title or d.update.title
    why = "\n".join(f"  - {x['name']}: {x['why']}" for x in deps if x.get("why"))
    steps = "\n".join(f"  - {s['action']}" + (f" ({s['department']})" if s.get("department") and department_id is None else "")
                      + (f", {t['by']} {s['due']}" if s.get("due") else "") for s in steps_for)
    cites = "\n".join(f"  [{i + 1}] {c.get('article') or ''} {c.get('eli') or c.get('source_url') or ''}"
                      for i, c in enumerate(d.citations))
    head = f"{t['for']}: {deps[0]['name']}\n" if department_id is not None else ""
    body = (f"{head}{title}\n{t['urgency']}: {t['urgencies'].get(d.urgency, d.urgency)}\n\n{d.summary}\n\n"
            + (f"{t['why']}:\n{why}\n\n" if why else "")
            + (f"{t['steps']}:\n{steps}\n\n" if steps else "")
            + f"{t['sources']}:\n{cites}\n\n"
            + t["reviewed"].format(who=a.reviewed_by.removeprefix("lawyer:"), date=f"{a.delivered_at:%d.%m.%Y}")
            + f"\n\n{schemas.DISCLAIMERS[lang]}")
    return schemas.EmailPreview(to=to, subject=f"[{t['subject']}] {title[:90]}", body_text=body)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
