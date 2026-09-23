"""AI step 3: draft a client-specific alert for a match (workstream 2). Pure function, no DB.

Output shape = the editable part of schemas.DraftOut:
  summary, affected_departments, next_steps, urgency, citations, model_version, prompt_version
"""
import json

from app.ai import llm, prompts
from app.ai.classify import update_for_prompt
from app.ai.matching import company_for_prompt

LANGUAGE_NAMES = {"DE": "German", "FR": "French", "EN": "English", "IT": "Italian"}


def route_departments(company: dict, classification: dict | None) -> list[dict]:
    """Deterministic routing: classified functional teams -> the company's departments."""
    teams = set((classification or {}).get("functional_teams", []))
    out = []
    for dep in company.get("departments", []):
        overlap = teams & set(dep.get("functions", []))
        if overlap:
            out.append({"department_id": dep["id"], "name": dep["name"],
                        "why": f"Covers {', '.join(sorted(overlap))}."})
    if not out and company.get("departments"):
        legal = next((d for d in company["departments"] if "Legal" in d.get("functions", [])), company["departments"][0])
        out.append({"department_id": legal["id"], "name": legal["name"], "why": "Default recipient (no specific team matched)."})
    return out


def draft(company: dict, update: dict, match: dict, revision_comment: str | None = None) -> dict:
    base = {"model_version": llm.model_version(), "prompt_version": prompts.DRAFT_VERSION}
    if llm.is_mock():
        return {**base, **_template(company, update, match)}

    articles = update.get("source_articles") or [{"ref": "(full text)", "text": (update.get("source_text") or "")[:6000]}]
    raw = llm.complete_json(
        prompts.DRAFT_SYSTEM,
        prompts.DRAFT_USER.format(
            company=company_for_prompt(company),
            departments=json.dumps([{"id": d["id"], "name": d["name"], "functions": d.get("functions", [])}
                                    for d in company.get("departments", [])], ensure_ascii=False),
            match_reason=match.get("llm_reason", ""),
            update=update_for_prompt(update, max_text=0),
            articles=json.dumps(articles[:25], ensure_ascii=False)[:12000],
            revision_note=f"The reviewing lawyer asked for a revision: {revision_comment}\n" if revision_comment else "",
            language=LANGUAGE_NAMES.get(company.get("preferred_language", "EN"), "English"),
        ),
        max_tokens=1200,
    )
    # TODO(ws2): validate citations against update["source_articles"] (ref exists, quote is a substring)
    return {
        **base,
        "summary": raw.get("summary", ""),
        "affected_departments": raw.get("affected_departments") or route_departments(company, update.get("classification")),
        "next_steps": raw.get("next_steps", []),
        "urgency": raw.get("urgency") if raw.get("urgency") in ("high", "medium", "low") else "medium",
        "citations": [{**c, "source_url": update.get("source_url")} for c in raw.get("citations", [])],
    }


def _template(company: dict, update: dict, match: dict) -> dict:
    """Mock draft: honest template text built only from metadata, clearly marked as such."""
    cls = update.get("classification") or {}
    deps = route_departments(company, cls)
    dates = []
    if update.get("entry_into_force_date"):
        dates.append(f"enters into force on {update['entry_into_force_date']}")
    if update.get("consultation_deadline"):
        dates.append(f"is open for consultation until {update['consultation_deadline']}")
    when = (" It " + " and ".join(dates) + ".") if dates else ""
    first_ref = (update.get("source_articles") or [{}])[0].get("ref")
    summary = (
        f"[Template draft - no LLM used] '{update['title']}' was published"
        f"{' on ' + update['publication_date'] if update.get('publication_date') else ''}.{when} "
        f"It was flagged for {company['name']} because: {match.get('llm_reason', '')}"
    )
    due = update.get("entry_into_force_date") or update.get("consultation_deadline")
    return {
        "summary": summary,
        "affected_departments": deps,
        "next_steps": [{"action": f"Check whether '{update['title'][:80]}' changes current processes.",
                        "department": d["name"], "due": due} for d in deps[:3]],
        "urgency": cls.get("urgency", "medium"),
        "citations": [{"claim": f"Publication{' and dates' if dates else ''} of '{update['title'][:80]}'.",
                       "eli": update.get("eli_uri"), "article": first_ref, "quote": None,
                       "source_url": update.get("source_url")}],
    }
