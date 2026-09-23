from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.models import Match, RegulatoryUpdate

router = APIRouter(prefix="/api/updates", tags=["updates"])


@router.get("", response_model=list[schemas.RegulatoryUpdateListItem])
def list_updates(update_type: str | None = None, simulated: bool | None = None, db: Session = Depends(get_db)):
    q = select(RegulatoryUpdate).order_by(RegulatoryUpdate.publication_date.desc())
    if update_type:
        q = q.where(RegulatoryUpdate.update_type == update_type)
    if simulated is not None:
        q = q.where(RegulatoryUpdate.is_simulated.is_(simulated))
    return db.scalars(q).all()


@router.get("/{update_id:path}/matches", response_model=list[schemas.MatchOut])
def update_matches(update_id: str, db: Session = Depends(get_db)):
    return db.scalars(select(Match).where(Match.update_id == update_id)).all()


@router.get("/{update_id:path}", response_model=schemas.RegulatoryUpdateOut)
def get_update(update_id: str, db: Session = Depends(get_db)):
    u = db.get(RegulatoryUpdate, update_id)
    if not u:
        raise HTTPException(404, "Update not found")
    return u
