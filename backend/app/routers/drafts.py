from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.deps import require_lawyer
from app.models import Alert, Draft
from app.services import review

router = APIRouter(prefix="/api", tags=["review"])


def _out(d: Draft) -> schemas.DraftOut:
    out = schemas.DraftOut.model_validate(d)
    out.warnings = review.warnings_for(d)
    return out


@router.get("/drafts", response_model=list[schemas.DraftOut])
def list_drafts(status: str | None = None, company_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Draft).order_by(Draft.created_at.desc())
    if status:
        q = q.where(Draft.status == status)
    if company_id:
        q = q.where(Draft.company_id == company_id)
    return [_out(d) for d in db.scalars(q)]


@router.get("/drafts/{draft_id}", response_model=schemas.DraftDetail)
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    d = db.get(Draft, draft_id)
    if not d:
        raise HTTPException(404, "Draft not found")
    return schemas.DraftDetail(
        **_out(d).model_dump(),
        update=schemas.RegulatoryUpdateOut.model_validate(d.update),
        match=schemas.MatchOut.model_validate(d.match),
        company=schemas.CompanyOut.model_validate(d.company),
    )


@router.put("/drafts/{draft_id}", response_model=schemas.DraftOut)
def edit_draft(draft_id: int, body: schemas.DraftEdit, db: Session = Depends(get_db), lawyer: str = Depends(require_lawyer)):
    return _out(review.edit(db, draft_id, body, lawyer))


@router.post("/drafts/{draft_id}/approve", response_model=schemas.AlertOut)
def approve(draft_id: int, body: schemas.ReviewDecision, db: Session = Depends(get_db), lawyer: str = Depends(require_lawyer)):
    return review.alert_out(review.approve(db, draft_id, lawyer, body.comment))


@router.post("/drafts/{draft_id}/reject", response_model=schemas.DraftOut)
def reject(draft_id: int, body: schemas.ReviewDecision, db: Session = Depends(get_db), lawyer: str = Depends(require_lawyer)):
    if not body.comment.strip():
        raise HTTPException(422, "A rejection needs a comment.")
    return _out(review.reject(db, draft_id, lawyer, body.comment))


@router.post("/drafts/{draft_id}/request-revision", response_model=schemas.DraftOut)
def request_revision(draft_id: int, body: schemas.ReviewDecision, db: Session = Depends(get_db),
                     lawyer: str = Depends(require_lawyer)):
    if not body.comment.strip():
        raise HTTPException(422, "A revision request needs a comment for the model.")
    return _out(review.request_revision(db, draft_id, lawyer, body.comment))


@router.get("/alerts/{alert_id}/email-preview", response_model=schemas.EmailPreview)
def email_preview(alert_id: int, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    return review.email_preview(a)
