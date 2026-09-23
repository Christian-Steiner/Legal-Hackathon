# Roadmap and task board

**Deadline: submission 15:30** (one person posts team name, members and track in the submissions channel).
The top 2 teams per track give a **3-minute live demo** plus Q&A.
Judging for Track 3: Problem–Solution Fit 35 % · **Responsible AI & Data Handling 30 %** · Creativity 20 % · Technical Depth 15 %.
Transparency, traceability, human oversight and honesty about limits beat feature count.

## Pipeline (what exists now)

```
 Fedlex SPARQL ──┐                       (company-independent)      (per company)            (per match)
 (AS, EIF,       ├─► ingest + dedup ─► 1 CLASSIFY ──────────► 2 MATCH rules → LLM ──► 3 DRAFT ──► 4 LAWYER REVIEW ──► 5 ALERT
  consultations) │   (one update per      topics, teams,        reason stored also       summary,      approve / edit /       client inbox,
 Organisers'  ───┘    ELI, sources          urgency, flags       for non-matches          departments,  reject / revision      grouped by dept,
 xlsx (simulated)     merged)                                                             steps, cites  (backend-enforced)     disclaimer, email preview
                                          every step ──► AUDIT LOG (actor, model + prompt version, Fedlex version)
```

Routing: the classifier assigns canonical **functional teams** (Legal, Compliance, Product…). Each client
department declares which functions it covers during onboarding, so teams map to concrete departments.
The same `functional_teams` output is what `scripts/evaluate.py` scores against the jury column.

The baseline runs fully end to end in mock mode, with real cached Fedlex data (99 items, 14 merged
duplicates), 4 demo companies and 8 simulated updates. Mock agreement with jury routing: **0.66 mean Jaccard**.

## Phases

| Phase | Until | Goal |
|---|---|---|
| 0 Base | done | Scaffold, contracts, end-to-end slice in mock mode |
| 1 Real core | ~13:00 | Real LLM (Apertus/OpenAI) for classify/match/draft; UI polished for the review flow; live ingest robust |
| 2 Depth | ~14:30 | Citation validation, translation next to source, eval ≥ 0.75, dedup demo, profile-change re-matching |
| 3 Freeze & demo | 15:15 | Feature freeze 14:45. Deploy, prepare a clean demo DB, rehearse the 3-min script, submit by 15:30 |

**Merge rhythm:** everyone works on a branch (`ws1/...`, `ws2/...`, `ws3/...`) and merges into `main` at least
at 12:00, 13:00, 14:00 and 14:45 (`git pull --rebase origin main`, run tests/build, push). Keep `main` green.

---

## WS1: Data & backend (Person A)
Owns `backend/app/ingest/`, `services/`, `routers/`, `models.py`, deployment.

| # | Task | Phase | Done when |
|---|---|---|---|
| 1.1 | Get Apertus + OpenAI keys (Keymaker: https://keymaker.ai-weeks.ch/), put them in `backend/.env`, share with WS2 | 1 | `.env` set on every laptop (not committed) |
| 1.2 | Make live ingest robust: retries/timeouts, `limit` params, log errors per item; refresh `data/fedlex_cache.json` shortly before the demo | 1 | "Ingest live" button works; cache refreshed |
| 1.3 | SR number + amended act: resolve `jolux:impacts` → consolidated act (cc) for AS publications; fill `sr_number` | 2 | SR shown on review screen |
| 1.4 | Dedup across sources: fuzzy key (SR number / normalised title) so the same change from 2 sources merges into one update with 2 `sources`. Add one hand-made duplicate to the dataset import to **demo** it | 2 | Updates page shows "2 merged" on a real example |
| 1.5 | Profile change → mark this company's matches stale + endpoint `POST /api/pipeline/match?company_id=` to re-run only that company | 2 | Edit profile → re-match → new drafts |
| 1.6 | Speed: run LLM calls concurrently (ThreadPool, max 5 req/s for Apertus) in `match_all` / `draft_all` | 2 | Full run < 2 min with a real LLM |
| 1.7 | Deploy to the Hostinger VPS (see `docs/DEPLOY.md`), HTTPS via the existing reverse proxy | 3 | Public URL works on a phone |
| 1.8 | Demo DB: script that seeds, runs the pipeline with the real LLM, and pre-approves 2–3 alerts so the inbox is not empty | 3 | `scripts/demo_reset.py` |

## WS2: AI & matching (Person B)
Owns `backend/app/ai/`, `scripts/evaluate.py`, `data/seed_companies.json`.

| # | Task | Phase | Done when |
|---|---|---|---|
| 2.1 | Switch to `LLM_PROVIDER=apertus` and check all three prompts return valid JSON (fallback: `openai`). Compare quality and pick one for the demo | 1 | `seed --pipeline` runs without errors with a real LLM |
| 2.2 | Improve classify prompt + taxonomy until `scripts/evaluate.py` ≥ 0.75 agreement; also score urgency; print per-row diffs | 1–2 | Number in README + a slide |
| 2.3 | Citation validation (`drafting.py` TODO): each citation's `article` must exist in `source_articles`, and each `quote` must be a substring of the source. Invalid → drop + add a warning in `review.warnings_for` | 2 | Review screen shows "unverified citation" |
| 2.4 | Drafting in the client's preferred language (DE/FR/EN) with the original shown next to it; optional Supertext translation of source articles for the reviewer (`SUPERTEXT_API_KEY`) | 2 | FR draft for Helvetia Pay |
| 2.5 | Inclusion topics (Jury Guide): make sure children's data, accessibility and nonprofit vulnerability are recognised and raise urgency; mention it in the reason | 2 | Evaluate shows R005/R006/R008 correct |
| 2.6 | Revision loop quality: the regenerated draft must address the lawyer comment (pass the previous draft + comment) | 2 | Demo: "make it shorter" works |
| 2.7 | Confidence/uncertainty: the model states what is unclear; low relevance → "FYI" instead of an action item | 2 | Field shown in review |

## WS3: Frontend (Person C)
Owns `frontend/src/`. **The review screen is the showcase.**

| # | Task | Phase | Done when |
|---|---|---|---|
| 3.1 | Review screen polish: clicking a citation scrolls to and highlights the article in the source panel; sticky action bar; keyboard-friendly | 1 | Smooth demo flow |
| 3.2 | Onboarding as a 4-step wizard (Company → Activities → Legal situation → Departments) with a privacy note ("we store company data only") | 1 | New client onboarded in < 1 min on stage |
| 3.3 | Client inbox: department tabs, urgency filter, mark as read, nicer email preview | 2 | |
| 3.4 | Transparency panel: pipeline view per update (ingest → classify → match → draft → review → alert) built from `/api/audit` | 2 | "Show me the trail" in 1 click |
| 3.5 | Revision diff (v1 vs v2) from `revision_history` | 2 | |
| 3.6 | Visual identity (LEXR-like, sober), responsive check on a phone, favicon, loading states | 2–3 | |
| 3.7 | Own the **3-min demo script** + slides (problem, flow, responsible AI, limits, eval score) | 3 | Rehearsed twice |

---

## 3-minute demo script (draft)
1. **Problem (20 s):** Swiss companies drown in Fedlex publications; LEXR can't read everything for every client.
2. **Onboarding (30 s):** a new client fills in its profile and departments.
3. **Pipeline (30 s):** "Run all" on real Fedlex data → classification → matching with written reasons (non-matches too).
4. **Review, the core (60 s):** lawyer opens a draft: summary next to the German source, citations highlight the
   article, rule hits + model/prompt version visible, missing-citation warning. Edit → request revision → approve.
5. **Client inbox (20 s):** alert under the right department, "Reviewed by LEXR on …", disclaimer, email preview.
6. **Trust (20 s):** audit log, Limitations page, eval score vs jury routing, Swiss-hosted Apertus model.

## Out of scope (say so on the Limitations page)
Real auth, real emails, EU/cantonal sources, soft law, automatic legal conclusions.
