"""Reset the DB and load demo companies. Optionally run the whole pipeline.

    uv run python -m scripts.seed            # companies only
    uv run python -m scripts.seed --pipeline # + ingest (cache) + classify + match + draft
"""
import json
import sys

from app import audit, schemas
from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine, init_db
from app.models import Company, Department
from app.services import pipeline


def main() -> None:
    Base.metadata.drop_all(engine)
    init_db()
    db = SessionLocal()
    for raw in json.loads((DATA_DIR / "seed_companies.json").read_text()):
        data = schemas.CompanyIn(**raw).model_dump()
        deps = data.pop("departments")
        c = Company(**data, departments=[Department(**d) for d in deps])
        db.add(c)
        db.flush()
        audit.log(db, actor="system:seed", action="company.onboarded", object_type="company", object_id=c.id,
                  details={"name": c.name})
    db.commit()
    print(f"Seeded {db.query(Company).count()} companies")
    if "--pipeline" in sys.argv:
        for res in pipeline.run_all(db):
            print(res.model_dump_json())
    db.close()


if __name__ == "__main__":
    main()
