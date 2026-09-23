"""Manually triggered pipeline steps (lawyer dashboard buttons)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.deps import require_lawyer
from app.ai.llm import LLMError
from app.models import AuditLogEntry
from app.services import pipeline

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.post("/pipeline/ingest/fedlex", response_model=schemas.PipelineResult)
def ingest_fedlex(live: bool | None = None, db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    """live=None -> follow DEMO_MODE; live=true forces the real SPARQL endpoint."""
    return pipeline.ingest_fedlex(db, live=live)


@router.post("/pipeline/ingest/dataset", response_model=schemas.PipelineResult)
def ingest_dataset(db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    return pipeline.ingest_dataset(db)


@router.post("/pipeline/classify", response_model=schemas.PipelineResult)
def classify(force: bool = False, db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    return pipeline.classify_all(db, force=force)


@router.post("/pipeline/match", response_model=schemas.PipelineResult)
def match(force: bool = False, db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    return pipeline.match_all(db, force=force)


@router.post("/pipeline/draft", response_model=schemas.PipelineResult)
def draft(db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    return pipeline.draft_all(db)


@router.post("/pipeline/process/{update_id:path}")
def process_update(update_id: str, db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    """Re-run classify -> match -> draft for ONE update with the current LLM (testing a provider)."""
    try:
        return pipeline.process_update(db, update_id)
    except KeyError:
        raise HTTPException(404, "Update not found")
    except LLMError as e:
        raise HTTPException(502, f"LLM call failed: {e}")


@router.post("/pipeline/run-all", response_model=list[schemas.PipelineResult])
def run_all(db: Session = Depends(get_db), _: str = Depends(require_lawyer)):
    return pipeline.run_all(db)


@router.get("/audit", response_model=list[schemas.AuditLogOut])
def audit_log(object_type: str | None = None, object_id: str | None = None, limit: int = 300,
              db: Session = Depends(get_db)):
    q = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(limit)
    if object_type:
        q = q.where(AuditLogEntry.object_type == object_type)
    if object_id:
        q = q.where(AuditLogEntry.object_id == object_id)
    return db.scalars(q).all()
