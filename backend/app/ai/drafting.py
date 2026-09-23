"""AI step 3: draft a client-specific alert for a match (workstream 2). Pure function, no DB.

Output shape = the editable part of schemas.DraftOut:
  title, summary, affected_departments, next_steps, urgency, citations, language, model_version, prompt_version
Everything client-facing is written in the client's preferred language (DE/FR/IT/EN).
"""
import json

from app.ai import llm, prompts
from app.ai.classify import update_for_prompt
from app.ai.matching import company_for_prompt

LANGUAGE_NAMES = {"DE": "German", "FR": "French", "EN": "English", "IT": "Italian"}


def language_of(company: dict) -> str:
    lang = company.get("preferred_language", "EN")
    return lang if lang in LANGUAGE_NAMES else "EN"


def route_departments(company: dict, classification: dict | None) -> list[dict]:
    """Deterministic routing: classified functional teams -> the company's departments."""
    t = TEMPLATE_TEXT[language_of(company)]
    teams = set((classification or {}).get("functional_teams", []))
    out = []
    for dep in company.get("departments", []):
        overlap = teams & set(dep.get("functions", []))
        if overlap:
            resp = t["resp"].format(r=dep["responsibilities"]) if dep.get("responsibilities") else ""
            out.append({"department_id": dep["id"], "name": dep["name"],
                        "why": t["why"].format(functions=", ".join(sorted(overlap)), company=company["name"], resp=resp)})
    if not out and company.get("departments"):
        legal = next((d for d in company["departments"] if "Legal" in d.get("functions", [])), company["departments"][0])
        out.append({"department_id": legal["id"], "name": legal["name"], "why": t["why_default"].format(company=company["name"])})
    return out


def draft(company: dict, update: dict, match: dict, revision_comment: str | None = None) -> dict:
    lang = language_of(company)
    base = {"model_version": llm.model_version(), "prompt_version": prompts.DRAFT_VERSION, "language": lang}
    if llm.is_mock():
        return {**base, **_template(company, update, match)}

    articles = update.get("source_articles") or [{"ref": "(full text)", "text": (update.get("source_text") or "")[:6000]}]
    raw = llm.complete_json(
        prompts.DRAFT_SYSTEM,
        prompts.DRAFT_USER.format(
            company=company_for_prompt(company),
            departments=json.dumps([{"id": d["id"], "name": d["name"], "functions": d.get("functions", []),
                                     "responsibilities": d.get("responsibilities", "")}
                                    for d in company.get("departments", [])], ensure_ascii=False),
            match_reason=match.get("llm_reason", ""),
            update=update_for_prompt(update, max_text=0),
            articles=json.dumps(articles[:25], ensure_ascii=False)[:12000],
            revision_note=f"The reviewing lawyer asked for a revision: {revision_comment}\n" if revision_comment else "",
            language=LANGUAGE_NAMES[lang],
        ),
        max_tokens=3000,  # deeper per-department reasons and 2-4 steps per department
    )
    # TODO(ws2): validate citations against update["source_articles"] (ref exists, quote is a substring)
    return {
        **base,
        "title": (raw.get("title") or "").strip() or None,
        "summary": raw.get("summary", ""),
        "affected_departments": raw.get("affected_departments") or route_departments(company, update.get("classification")),
        "next_steps": raw.get("next_steps", []),
        "urgency": raw.get("urgency") if raw.get("urgency") in ("high", "medium", "low") else "medium",
        "citations": [{**c, "source_url": update.get("source_url")} for c in raw.get("citations", [])],
    }


# Mock-mode wording per client language. Templates only restate metadata; they never interpret the law.
TEMPLATE_TEXT = {
    "EN": {
        "prefix": "[Template draft - no LLM used]",
        "published": "'{title}' was published{on}.", "on": " on {date}",
        "subject": "It", "eif": "enters into force on {date}", "cons": "is open for consultation until {date}", "and": " and ",
        "flagged": "It was flagged for {company} because: {reason}",
        "flagged_generic": "It was flagged as relevant for {company} based on its company profile.",
        "why": ("The update was classified as relevant for {functions}, which this department covers at {company}{resp}. "
                "Check whether the cited provisions change its processes; this template was generated without an LLM "
                "and cannot assess the legal text itself."),
        "resp": " (responsibilities: {r})",
        "why_default": ("Default recipient: no department at {company} matched the update's classified teams, "
                        "so it goes to this department for a first check."),
        "steps": ["Read the cited provisions of '{title}' and list which {dept} processes, documents or controls they touch.",
                  "Assess with LEXR whether {dept} needs to change any of these, and what is still unclear.",
                  "Assign an owner in {dept} to follow up and track any required changes."],
        "claim": "Publication{dates} of '{title}'.", "claim_dates": " and dates",
    },
    "DE": {
        "prefix": "[Vorlage - ohne KI erstellt]",
        "published": "«{title}» wurde{on} veröffentlicht.", "on": " am {date}",
        "subject": "Die Änderung", "eif": "tritt am {date} in Kraft", "cons": "ist bis am {date} in der Vernehmlassung",
        "and": " und ",
        "flagged": "Sie wurde für {company} markiert, weil: {reason}",
        "flagged_generic": "Sie wurde aufgrund des Unternehmensprofils von {company} als relevant markiert.",
        "why": ("Die Änderung wurde als relevant für {functions} eingestuft - Bereiche, die diese Abteilung bei {company} "
                "abdeckt{resp}. Prüfen Sie, ob die zitierten Bestimmungen ihre Abläufe verändern; diese Vorlage wurde "
                "ohne KI erstellt und kann den Rechtstext selbst nicht beurteilen."),
        "resp": " (Aufgaben: {r})",
        "why_default": ("Standardempfänger: Keine Abteilung von {company} passt zu den zugeordneten Teams der Änderung, "
                        "deshalb geht sie zur ersten Prüfung an diese Abteilung."),
        "steps": ["Die zitierten Bestimmungen von «{title}» lesen und festhalten, welche Abläufe, Dokumente oder "
                  "Kontrollen von {dept} betroffen sind.",
                  "Mit LEXR klären, ob {dept} etwas davon ändern muss und welche Punkte noch unklar sind.",
                  "In {dept} eine verantwortliche Person bestimmen, die nötige Änderungen verfolgt."],
        "claim": "Veröffentlichung{dates} von «{title}».", "claim_dates": " und Daten",
    },
    "FR": {
        "prefix": "[Modèle - généré sans IA]",
        "published": "«{title}» a été publié{on}.", "on": " le {date}",
        "subject": "Le texte", "eif": "entre en vigueur le {date}", "cons": "est en consultation jusqu'au {date}",
        "and": " et ",
        "flagged": "Il a été signalé pour {company} parce que : {reason}",
        "flagged_generic": "Il a été signalé comme pertinent pour {company} sur la base de son profil d'entreprise.",
        "why": ("La modification a été classée comme pertinente pour {functions}, domaines que ce département couvre "
                "chez {company}{resp}. Vérifiez si les dispositions citées modifient ses processus ; ce modèle a été "
                "généré sans IA et ne peut pas évaluer le texte juridique lui-même."),
        "resp": " (responsabilités : {r})",
        "why_default": ("Destinataire par défaut : aucun département de {company} ne correspond aux équipes attribuées "
                        "à la modification ; elle est donc transmise à ce département pour un premier examen."),
        "steps": ["Lire les dispositions citées de «{title}» et lister les processus, documents ou contrôles de {dept} "
                  "concernés.",
                  "Évaluer avec LEXR si {dept} doit modifier certains de ces éléments et ce qui reste incertain.",
                  "Désigner un responsable au sein de {dept} pour suivre les modifications nécessaires."],
        "claim": "Publication{dates} de «{title}».", "claim_dates": " et dates",
    },
    "IT": {
        "prefix": "[Modello - generato senza IA]",
        "published": "«{title}» è stato pubblicato{on}.", "on": " il {date}",
        "subject": "Il testo", "eif": "entra in vigore il {date}", "cons": "è in consultazione fino al {date}",
        "and": " e ",
        "flagged": "È stato segnalato per {company} perché: {reason}",
        "flagged_generic": "È stato segnalato come rilevante per {company} in base al profilo aziendale.",
        "why": ("La modifica è stata classificata come rilevante per {functions}, ambiti che questo reparto copre presso "
                "{company}{resp}. Verificate se le disposizioni citate modificano i suoi processi; questo modello è "
                "stato generato senza IA e non può valutare il testo giuridico."),
        "resp": " (compiti: {r})",
        "why_default": ("Destinatario predefinito: nessun reparto di {company} corrisponde ai team attribuiti alla "
                        "modifica, quindi viene inoltrata a questo reparto per una prima verifica."),
        "steps": ["Leggere le disposizioni citate di «{title}» ed elencare quali processi, documenti o controlli di "
                  "{dept} sono interessati.",
                  "Valutare con LEXR se {dept} deve modificare qualcuno di questi elementi e cosa resta poco chiaro.",
                  "Nominare un responsabile in {dept} che segua le modifiche necessarie."],
        "claim": "Pubblicazione{dates} di «{title}».", "claim_dates": " e date",
    },
}


def _template(company: dict, update: dict, match: dict) -> dict:
    """Mock draft: honest template text built only from metadata, clearly marked as such.
    The official title stays untranslated (no LLM to translate it)."""
    lang = language_of(company)
    t = TEMPLATE_TEXT[lang]
    cls = update.get("classification") or {}
    deps = route_departments(company, cls)
    title = update["title"]
    short = title[:80]
    dates = []
    if update.get("entry_into_force_date"):
        dates.append(t["eif"].format(date=update["entry_into_force_date"]))
    if update.get("consultation_deadline"):
        dates.append(t["cons"].format(date=update["consultation_deadline"]))
    when = f" {t['subject']} {t['and'].join(dates)}." if dates else ""
    on = t["on"].format(date=update["publication_date"]) if update.get("publication_date") else ""
    # Match reasons are written in English, so other languages get a generic sentence instead.
    flagged = (t["flagged"].format(company=company["name"], reason=match.get("llm_reason", ""))
               if lang == "EN" and match.get("llm_reason") else t["flagged_generic"].format(company=company["name"]))
    summary = f"{t['prefix']} {t['published'].format(title=title, on=on)}{when} {flagged}"
    first_ref = (update.get("source_articles") or [{}])[0].get("ref")
    due = update.get("entry_into_force_date") or update.get("consultation_deadline")
    return {
        "title": None,
        "summary": summary,
        "affected_departments": deps,
        "next_steps": [{"action": s.format(title=short, dept=d["name"]), "department": d["name"], "due": due}
                       for d in deps for s in t["steps"]],
        "urgency": cls.get("urgency", "medium"),
        "citations": [{"claim": t["claim"].format(dates=t["claim_dates"] if dates else "", title=short),
                       "eli": update.get("eli_uri"), "article": first_ref, "quote": None,
                       "source_url": update.get("source_url")}],
    }
