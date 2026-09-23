"""AI step 2: does update X matter to company Y? (workstream 2)
Rules first (transparent, cheap), then the LLM for candidates. Pure function, no DB."""
import json

from app.ai import llm, prompts, rules
from app.ai.classify import update_for_prompt

# Below this rule score we do not spend an LLM call; the non-match is stored with the rule reason.
LLM_CANDIDATE_THRESHOLD = 0.2
MOCK_MATCH_THRESHOLD = 0.4


def company_for_prompt(company: dict) -> str:
    keep = ["name", "industry", "description", "size_band", "hq_canton", "jurisdictions", "flags",
            "legal_context", "key_challenges", "topics"]
    d = {k: company.get(k) for k in keep}
    d["flags"] = [k for k, v in (company.get("flags") or {}).items() if v]
    d["departments"] = [dep["name"] for dep in company.get("departments", [])]
    return json.dumps(d, ensure_ascii=False, indent=1)


def match(company: dict, update: dict) -> dict:
    """Returns dict with keys: matched, relevance_score, rule_hits, llm_reason, model_version, prompt_version."""
    hits = rules.profile_rules(company, update, update.get("classification"))
    rule_score = rules.score(hits)
    base = {"rule_hits": hits, "prompt_version": prompts.MATCH_VERSION}

    if rule_score < LLM_CANDIDATE_THRESHOLD:
        return {**base, "matched": False, "relevance_score": rule_score, "model_version": "rules-v1",
                "llm_reason": "Not relevant: no profile rule matched strongly enough"
                              + (f" ({'; '.join(h['detail'] for h in hits)})" if hits else "") + ". No LLM call made."}

    if llm.is_mock():
        matched = rule_score >= MOCK_MATCH_THRESHOLD
        reason = ("Relevant because: " if matched else "Weak signal only: ") + " ".join(h["detail"] for h in hits)
        return {**base, "matched": matched, "relevance_score": rule_score, "llm_reason": reason,
                "model_version": llm.model_version()}

    raw = llm.complete_json(
        prompts.MATCH_SYSTEM,
        prompts.MATCH_USER.format(company=company_for_prompt(company), update=update_for_prompt(update, max_text=1200),
                                  rule_hits=json.dumps(hits, ensure_ascii=False)),
        max_tokens=250,
    )
    return {**base, "matched": bool(raw.get("relevant")), "relevance_score": float(raw.get("relevance_score", rule_score)),
            "llm_reason": raw.get("reason", "(model gave no reason)"), "model_version": llm.model_version()}
