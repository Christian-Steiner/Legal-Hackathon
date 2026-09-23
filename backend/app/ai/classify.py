"""AI step 1: company-independent classification of an update (workstream 2).
Pure function: dict in, dict out (shape = schemas.Classification). No DB access."""
import json
from datetime import date, datetime, timezone

from app.ai import llm, prompts, rules
from app.schemas import ACTIVITY_FLAGS, APPLICABILITY_SCOPES, FUNCTIONAL_TEAMS


def update_for_prompt(update: dict, max_text: int = 2000) -> str:
    keep = ["title", "update_type", "jurisdiction", "eli_uri", "publication_date",
            "entry_into_force_date", "consultation_deadline", "source_language", "metadata_extra"]
    d = {k: update.get(k) for k in keep if update.get(k)}
    if update.get("source_text"):
        d["source_text_excerpt"] = update["source_text"][:max_text]
    return json.dumps(d, ensure_ascii=False, indent=1)


def classify(update: dict, today: date | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    today = today or date.today()
    if llm.is_mock():
        out = _heuristic(update)
    else:
        raw = llm.complete_json(
            prompts.CLASSIFY_SYSTEM,
            prompts.CLASSIFY_USER.format(update=update_for_prompt(update), teams=FUNCTIONAL_TEAMS, today=today.isoformat(),
                                         flags="\n".join(f"- {k}: {v}" for k, v in ACTIVITY_FLAGS.items()),
                                         scopes="\n".join(f"- {k}: {v}" for k, v in APPLICABILITY_SCOPES.items())),
            max_tokens=450,
        )
        out = {
            "topics": raw.get("topics", []),
            "functional_teams": [t for t in raw.get("functional_teams", []) if t in FUNCTIONAL_TEAMS],
            "triggered_flags": [f for f in raw.get("triggered_flags", []) if f in ACTIVITY_FLAGS],
            "affected_business_types": raw.get("affected_business_types", []),
            "applies_to": [a for a in raw.get("applies_to", []) if a in APPLICABILITY_SCOPES],
            "urgency": raw.get("urgency") if raw.get("urgency") in ("high", "medium", "low") else "medium",
            "rationale": raw.get("rationale", ""),
        }
    out["urgency"], note = rules.apply_deadline_floor(out["urgency"], update, today)
    if note:
        out["rationale"] = f"{out['rationale']} {note}".strip()
    return {**out, "model_version": llm.model_version(), "prompt_version": prompts.CLASSIFY_VERSION, "classified_at": now}


def _heuristic(update: dict) -> dict:
    meta = update.get("metadata_extra") or {}
    text = " ".join(str(x) for x in [update.get("title"), meta.get("topic_area"), meta.get("affected_business_types"),
                                    (update.get("source_text") or "")[:3000]] if x)
    hits = rules.keyword_scan(text)
    # General scope only from the title: an AML act that merely mentions beneficial owners in its body
    # does not bind every company, the act on the transparency of legal entities does.
    title_topics = rules.keyword_scan(" ".join(str(x) for x in [update.get("title"), meta.get("topic_area")] if x))
    scopes = []
    for topic in title_topics:
        scopes += [x for x in rules.SCOPE_BY_TOPIC.get(topic, []) if x not in scopes]
    topics, flags, teams = [], [], []
    for topic in hits:
        _, f, t = rules.TAXONOMY[topic]
        topics.append(topic)
        flags += [x for x in f if x not in flags]
        teams += [x for x in t if x not in teams]
    if meta.get("topic_area") and meta["topic_area"] not in topics:
        topics.append(meta["topic_area"])
    urgency = meta.get("urgency_level") or ("medium" if update.get("update_type") != "consultation" else "low")
    business_types = [s.strip() for s in str(meta.get("affected_business_types", "")).split(";") if s.strip()]
    return {
        "topics": topics,
        "functional_teams": teams or ["Legal"],
        "triggered_flags": flags,
        "affected_business_types": business_types,
        "applies_to": scopes,
        "urgency": urgency,
        "rationale": f"Keyword heuristic matched: {', '.join(topics) or 'nothing specific'}." ,
    }
