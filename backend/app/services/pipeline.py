"""Orchestration: ingest -> classify -> match -> draft. Owns DB writes + audit entries.
The AI functions it calls (app/ai/*) are pure and DB-free."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, schemas
from app.ai import classify as ai_classify
from app.ai import drafting as ai_drafting
from app.ai import matching as ai_matching
from app.ai.llm import LLMError
from app.config import settings
from app.ingest import dataset, fedlex
from app.models import Company, Draft, Match, RegulatoryUpdate


def dedup_key(item: dict) -> str:
    """Same legal change reported by several sources -> same key -> one RegulatoryUpdate row.
    TODO(ws1): once a second real source exists, add fuzzy matching (SR number, normalised title)."""
    if item.get("eli_uri"):
        return item["eli_uri"].rstrip("/")
    return f"{item['source']}:{item['external_id']}"


def upsert_items(db: Session, items: list[dict], actor: str = "system") -> schemas.PipelineResult:
    res = schemas.PipelineResult(step="ingest")
    for it in items:
        key = dedup_key(it)
        src = {"source": it["source"], "external_id": it["external_id"], "url": it.get("source_url"),
               "version": it.get("source_version"), "fetched_at": it["fetched_at"], "kind": it["update_type"]}
        existing = db.scalar(select(RegulatoryUpdate).where(RegulatoryUpdate.dedup_key == key))
        if existing:
            if not any(s["source"] == src["source"] and s.get("kind") == src["kind"] for s in existing.sources):
                existing.sources = [*existing.sources, src]
                audit.log(db, actor=actor, action="ingest.merged_source", object_type="update", object_id=existing.id,
                          details={"source": src})
                res.updated += 1
            else:
                res.skipped += 1
            # fill gaps (e.g. text fetched later / EIF date from the second query)
            for field in ("entry_into_force_date", "consultation_deadline", "source_text", "source_text_url"):
                if not getattr(existing, field) and it.get(field):
                    setattr(existing, field, it[field])
            if not existing.source_articles and it.get("source_articles"):
                existing.source_articles = it["source_articles"]
            continue
        upd = RegulatoryUpdate(
            id=f"{it['source'] if it['source'] != 'organisers_dataset' else 'dataset'}:{it['external_id']}",
            dedup_key=key,
            eli_uri=it.get("eli_uri"),
            sr_number=it.get("sr_number"),
            title=it["title"],
            update_type=it["update_type"],
            jurisdiction=it.get("jurisdiction", "CH"),
            publication_date=it.get("publication_date"),
            entry_into_force_date=it.get("entry_into_force_date"),
            consultation_deadline=it.get("consultation_deadline"),
            source_language=it.get("source_language", "DE"),
            source_text=it.get("source_text"),
            source_articles=it.get("source_articles") or [],
            source_text_url=it.get("source_text_url"),
            source_url=it.get("source_url"),
            source_version=it.get("source_version"),
            sources=[src],
            is_simulated=it.get("is_simulated", False),
            metadata_extra=it.get("metadata_extra") or {},
            fetched_at=datetime.fromisoformat(it["fetched_at"]),
        )
        db.add(upd)
        db.flush()
        audit.log(db, actor=actor, action="ingest.created", object_type="update", object_id=upd.id,
                  details={"source": it["source"], "source_version": it.get("source_version"), "eli": it.get("eli_uri")})
        res.created += 1
    db.commit()
    return res


def ingest_fedlex(db: Session, live: bool | None = None) -> schemas.PipelineResult:
    live = (not settings.demo_mode) if live is None else live
    items = fedlex.fetch_live() if live else fedlex.load_cache()
    items = items[:2]  # limit number of regulatory changes for demo version
    res = upsert_items(db, items)
    res.step = "ingest_fedlex"
    res.info = {"mode": "live" if live else "cache", "items": len(items)}
    return res


def ingest_dataset(db: Session) -> schemas.PipelineResult:
    res = upsert_items(db, dataset.load_items()[:2])
    res.step = "ingest_dataset"
    return res


def _pmap(fn, items: list) -> list:
    """Run the (pure, DB-free) AI function over items in parallel. Returns results or the exception
    per item, in order. DB writes stay on the calling thread."""
    def safe(x):
        try:
            return fn(*x) if isinstance(x, tuple) else fn(x)
        except LLMError as e:
            return e
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max(1, settings.llm_concurrency)) as pool:
        return list(pool.map(safe, items))


def _update_dict(u: RegulatoryUpdate) -> dict:
    return schemas.RegulatoryUpdateOut.model_validate(u).model_dump(mode="json")


def _company_dict(c: Company) -> dict:
    return schemas.CompanyOut.model_validate(c).model_dump(mode="json")


def classify_all(db: Session, force: bool = False) -> schemas.PipelineResult:
    res = schemas.PipelineResult(step="classify")
    todo = []
    for u in db.scalars(select(RegulatoryUpdate)):
        if u.classification and not force:
            res.skipped += 1
        else:
            todo.append(u)
    print(f"\n[Classify] Classifying {len(todo)} updates ({res.skipped} already done)...", flush=True)
    outs = _pmap(ai_classify.classify, [_update_dict(u) for u in todo])
    for u, out in zip(todo, outs):
        if isinstance(out, Exception):
            print(f"  [ERROR] Classify failed for {u.id}: {out}", flush=True)
            res.errors.append(f"{u.id}: {out}")
            continue
        _classify_one(db, u, out)
        res.created += 1
    db.commit()
    print(f"[Classify] Done: {res.created} created, {res.skipped} skipped, {len(res.errors)} errors.", flush=True)
    return res


def _classify_one(db: Session, u: RegulatoryUpdate, out: dict | None = None) -> None:
    """Store a classification (computed here if not given). Raises LLMError."""
    u.classification = out if out is not None else ai_classify.classify(_update_dict(u))
    audit.log(db, actor=f"model:{u.classification['model_version']}", action="classify", object_type="update",
              object_id=u.id, details=u.classification)


def _approved(db: Session, m: Match | None) -> bool:
    d = m and db.scalar(select(Draft).where(Draft.match_id == m.id))
    return bool(d and d.status == "approved")


def _match_one(db: Session, u: RegulatoryUpdate, ud: dict, c: Company, existing: Match | None,
               out: dict | None = None) -> Match | None:
    """(Re-)match one update to one company. Returns None if skipped. Raises LLMError."""
    if _approved(db, existing):
        return None  # never silently change something a lawyer already approved
    if out is None:
        out = ai_matching.match(_company_dict(c), ud)
    if existing:
        old_draft = db.scalar(select(Draft).where(Draft.match_id == existing.id))
        if old_draft:
            db.delete(old_draft)
    m = existing or Match(update_id=u.id, company_id=c.id)
    for k, v in out.items():
        setattr(m, k, v)
    db.add(m)
    db.flush()
    audit.log(db, actor=f"model:{out['model_version']}", action="match", object_type="match", object_id=m.id,
              details={"update_id": u.id, "company_id": c.id, **out})
    return m


def process_update(db: Session, update_id: str, company_ids: list[int] | None = None) -> dict:
    """Run ONE update through classify -> match -> draft with the current LLM provider, re-doing
    earlier results (approved drafts are left untouched). For testing a provider on a single
    incoming change without re-running the whole pipeline. Raises LLMError / KeyError."""
    u = db.get(RegulatoryUpdate, update_id)
    if u is None:
        raise KeyError(update_id)
    _classify_one(db, u)
    db.commit()
    ud = _update_dict(u)
    q = select(Company)
    if company_ids:
        q = q.where(Company.id.in_(company_ids))
    results = []
    for c in db.scalars(q):
        existing = db.scalar(select(Match).where(Match.update_id == u.id, Match.company_id == c.id))
        m = _match_one(db, u, ud, c, existing)
        if m is None:
            results.append({"company": c.name, "skipped": "draft already approved"})
            continue
        d = draft_for_match(db, m) if m.matched else None
        db.commit()
        results.append({"company": c.name, "matched": m.matched, "score": m.relevance_score, "reason": m.llm_reason,
                        "draft_id": d.id if d else None})
    return {"update_id": u.id, "title": u.title, "model": u.classification["model_version"],
            "classification": u.classification, "companies": results}


def match_all(db: Session, force: bool = False) -> schemas.PipelineResult:
    res = schemas.PipelineResult(step="match")
    companies = list(db.scalars(select(Company)))
    cds = {c.id: _company_dict(c) for c in companies}
    todo = []  # (update, update_dict, company, existing match)
    for u in db.scalars(select(RegulatoryUpdate).where(RegulatoryUpdate.classification.is_not(None))):
        ud = _update_dict(u)
        for c in companies:
            existing = db.scalar(select(Match).where(Match.update_id == u.id, Match.company_id == c.id))
            if (existing and not force) or _approved(db, existing):
                res.skipped += 1
            else:
                todo.append((u, ud, c, existing))
    print(f"\n[Match] Matching {len(todo)} update/company pairs ({res.skipped} skipped)...", flush=True)
    outs = _pmap(ai_matching.match, [(cds[c.id], ud) for u, ud, c, _ in todo])
    for (u, ud, c, existing), out in zip(todo, outs):
        if isinstance(out, Exception):
            print(f"  [ERROR] Match failed for {u.id}/{c.id}: {out}", flush=True)
            res.errors.append(f"{u.id}/{c.id}: {out}")
            continue
        m = _match_one(db, u, ud, c, existing, out)
        res.created += 1
        print(f"  {'MATCH   ' if m.matched else 'NO MATCH'} ({m.relevance_score:.2f}) {c.name} <- {u.title[:50]}", flush=True)
    db.commit()
    matched_count = db.query(Match).filter(Match.matched.is_(True)).count()
    res.info = {"matched": matched_count}
    print(f"[Match] Done: {res.created} evaluated, {matched_count} matches found.", flush=True)
    return res


def _draft_inputs(m: Match) -> tuple:
    return (_company_dict(m.company), _update_dict(m.update), schemas.MatchOut.model_validate(m).model_dump(mode="json"))


def draft_for_match(db: Session, m: Match, revision_comment: str | None = None, actor_note: str = "generated",
                    out: dict | None = None) -> Draft:
    """Create (or regenerate) the draft for a match. Raises LLMError."""
    if out is None:
        out = ai_drafting.draft(*_draft_inputs(m), revision_comment)
    now = datetime.now(timezone.utc)
    d = db.scalar(select(Draft).where(Draft.match_id == m.id))
    editable = {k: out[k] for k in ("summary", "affected_departments", "next_steps", "urgency", "citations")}
    if d is None:
        d = Draft(match_id=m.id, company_id=m.company_id, update_id=m.update_id, version=1, status="pending",
                  revision_history=[], reviewer_comments=[], model_version=out["model_version"], prompt_version=out["prompt_version"], **editable)
        db.add(d)
    else:
        d.version += 1
        d.status = "pending"
        d.edited_by_lawyer = False
        d.model_version, d.prompt_version = out["model_version"], out["prompt_version"]
        for k, v in editable.items():
            setattr(d, k, v)
    d.revision_history = [*d.revision_history, {"version": d.version, "at": now.isoformat(), "by": f"model:{out['model_version']}",
                                                "change": actor_note, "snapshot": editable}]
    db.flush()
    audit.log(db, actor=f"model:{out['model_version']}", action=f"draft.{actor_note}", object_type="draft", object_id=d.id,
              details={"version": d.version, "prompt_version": out["prompt_version"], "revision_comment": revision_comment,
                       "update_source_version": m.update.source_version})
    return d


def draft_all(db: Session) -> schemas.PipelineResult:
    res = schemas.PipelineResult(step="draft")
    todo = []
    for m in db.scalars(select(Match).where(Match.matched.is_(True))):
        if db.scalar(select(Draft).where(Draft.match_id == m.id)):
            res.skipped += 1
        else:
            todo.append(m)
    print(f"\n[Draft] Generating {len(todo)} drafts ({res.skipped} already exist)...", flush=True)
    outs = _pmap(ai_drafting.draft, [_draft_inputs(m) for m in todo])
    for m, out in zip(todo, outs):
        if isinstance(out, Exception):
            print(f"  [ERROR] Draft failed for match {m.id}: {out}", flush=True)
            res.errors.append(f"match {m.id}: {out}")
            continue
        draft_for_match(db, m, out=out)
        res.created += 1
    db.commit()
    print(f"[Draft] Done: {res.created} drafts created, {res.skipped} skipped, {len(res.errors)} errors.", flush=True)
    return res


def run_all(db: Session) -> list[schemas.PipelineResult]:
    return [ingest_fedlex(db), ingest_dataset(db), classify_all(db), match_all(db), draft_all(db)]
