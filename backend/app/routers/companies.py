from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, schemas
from app.db import get_db
from app.deps import actor
from app.models import Alert, Company, Department, Match
from app.services import review

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[schemas.CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.scalars(select(Company).order_by(Company.id)).all()


@router.get("/{company_id}", response_model=schemas.CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c


@router.post("", response_model=schemas.CompanyOut, status_code=201)
def create_company(body: schemas.CompanyIn, db: Session = Depends(get_db), who: str = Depends(actor)):
    data = body.model_dump()
    deps = data.pop("departments")
    c = Company(**data, departments=[Department(**d) for d in deps])
    db.add(c)
    db.flush()
    audit.log(db, actor=who, action="company.onboarded", object_type="company", object_id=c.id, details={"name": c.name})
    db.commit()
    return c


@router.put("/{company_id}", response_model=schemas.CompanyOut)
def update_company(company_id: int, body: schemas.CompanyIn, db: Session = Depends(get_db), who: str = Depends(actor)):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    data = body.model_dump()
    deps = data.pop("departments")
    for k, v in data.items():
        setattr(c, k, v)
    # Keep ids of departments whose name is unchanged (drafts/alerts reference department_id).
    by_name = {d.name: d for d in c.departments}
    new_deps = []
    for d in deps:
        existing = by_name.get(d["name"])
        if existing:
            for k, v in d.items():
                setattr(existing, k, v)
            new_deps.append(existing)
        else:
            new_deps.append(Department(**d))
    c.departments = new_deps
    audit.log(db, actor=who, action="company.updated", object_type="company", object_id=c.id, details={"fields": list(data)})
    db.commit()
    # TODO(ws1): profile changed -> matches for this company are stale; offer "re-run matching".
    return c


@router.get("/{company_id}/alerts", response_model=list[schemas.AlertOut])
def company_alerts(company_id: int, db: Session = Depends(get_db)):
    alerts = db.scalars(select(Alert).where(Alert.company_id == company_id).order_by(Alert.delivered_at.desc())).all()
    return [review.alert_out(a) for a in alerts]


@router.get("/{company_id}/matches", response_model=list[schemas.MatchOut])
def company_matches(company_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Match).where(Match.company_id == company_id)).all()
