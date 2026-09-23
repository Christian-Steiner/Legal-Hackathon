# Contracts between workstreams

Source of truth: `backend/app/schemas.py`. Hand-written mirror: `frontend/src/types.ts`.
Live, always-current reference: run the backend and open http://localhost:8000/docs (OpenAPI).

## Key shapes (abridged)

**RegulatoryUpdate** (`GET /api/updates/{id}`)
```json
{
  "id": "fedlex:oc/2026/322",
  "dedup_key": "https://fedlex.data.admin.ch/eli/oc/2026/322",
  "eli_uri": "https://fedlex.data.admin.ch/eli/oc/2026/322",
  "sr_number": null,
  "title": "Bundesgesetz über die Bekämpfung der Geldwäscherei …",
  "update_type": "as_publication | entry_into_force | consultation | simulated",
  "jurisdiction": "CH",
  "publication_date": "2026-06-16", "entry_into_force_date": "2026-10-01", "consultation_deadline": null,
  "source_language": "DE",
  "source_text": "…", "source_articles": [{"ref": "Art. 2", "text": "…"}],
  "source_url": "…", "source_text_url": "…/html/…", "source_version": "2026-06-16T15:28:13.119+02:00",
  "sources": [{"source": "fedlex", "external_id": "oc/2026/322", "kind": "entry_into_force", "fetched_at": "…"}],
  "is_simulated": false,
  "classification": {"topics": ["financial market regulation"], "functional_teams": ["Compliance", "Legal"],
                     "triggered_flags": ["finma_supervised"], "urgency": "medium", "rationale": "…",
                     "model_version": "…", "prompt_version": "classify-v1", "classified_at": "…"}
}
```

**Draft** (`GET /api/drafts/{id}` also embeds `update`, `match`, `company`)
```json
{
  "id": 20, "match_id": 41, "company_id": 2, "update_id": "fedlex:oc/2026/322", "version": 1,
  "summary": "…",
  "affected_departments": [{"department_id": 6, "name": "Compliance & AML", "why": "…"}],
  "next_steps": [{"action": "…", "department": "Compliance & AML", "due": "2026-10-01"}],
  "urgency": "high | medium | low",
  "citations": [{"claim": "…", "eli": "https://fedlex…/eli/oc/2026/322", "article": "Art. 2", "quote": "…", "source_url": "…"}],
  "status": "pending | approved | rejected | revision_requested",
  "reviewer_comments": [], "revision_history": [{"version": 1, "by": "model:…", "change": "generated", "snapshot": {}}],
  "title": "Client-facing title in the draft language (null before draft-v2 -> use update.title)",
  "language": "DE | FR | IT | EN (the client's preferred language; every text field is in it)",
  "model_version": "apertus:swiss-ai/Apertus-v1.5-70B", "prompt_version": "draft-v2",
  "warnings": ["NO_CITATIONS: …"]
}
```

## Endpoints
| Method | Path | Who |
|---|---|---|
| GET | `/api/meta` | vocabularies (teams, flags, cantons), demo mode, model |
| GET/POST | `/api/companies` · GET/PUT `/api/companies/{id}` | client onboarding/profile |
| GET | `/api/companies/{id}/alerts` · `/matches` | client inbox |
| GET | `/api/updates` · `/api/updates/{id}` · `/api/updates/{id}/matches` | |
| GET | `/api/drafts?status=&company_id=` · `/api/drafts/{id}` | review queue / screen |
| PUT | `/api/drafts/{id}` | lawyer edit |
| POST | `/api/drafts/{id}/approve` · `/reject` · `/request-revision` (body `{comment}`) | lawyer only |
| GET | `/api/alerts/{id}/email-preview?department_id=` | in the alert's language; with `department_id` only that department's part |
| POST | `/api/pipeline/ingest/fedlex?live=` · `ingest/dataset` · `classify` · `match` · `draft` · `run-all` | lawyer only |
| GET | `/api/audit?object_type=&object_id=&limit=` | |

Lawyer-only endpoints require headers `X-Role: lawyer` and `X-Actor: <name>` (demo stand-in for auth;
the frontend role switcher sends them).

**Alert** (`GET /api/companies/{id}/alerts`) also carries `language`; `title` and `disclaimer` are in that language.
Each department sees only its own `departments[].why` and the `next_steps` whose `department` is its name.
