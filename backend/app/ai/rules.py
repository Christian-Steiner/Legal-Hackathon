"""Deterministic layer (workstream 2): keyword taxonomy + profile rules.

Used (a) as the first, transparent matching step before the LLM and
(b) as the whole classifier/matcher when LLM_PROVIDER=mock.
TODO(ws2): extend the taxonomy; tune weights; add rules for jurisdictions/size/canton.
"""
import re
from datetime import date

from app.schemas import APPLICABILITY_SCOPES

# topic -> (keyword regexes in DE/FR/IT/EN, activity flags it concerns, functional teams)
TAXONOMY: dict[str, tuple[list[str], list[str], list[str]]] = {
    "data protection": (
        [r"datenschutz", r"personendaten", r"protection des données", r"protezione dei dati",
         r"personal data", r"data protection", r"privacy", r"analytics", r"profiling"],
        ["processes_personal_data", "customer_profiling"], ["Legal", "Data", "Security"]),
    "AI governance": (
        [r"künstliche intelligenz", r"intelligence artificielle", r"\bKI\b", r"\bAI\b", r"artificial intelligence",
         r"high-risk ai", r"algorithm"],
        ["offers_ai_features"], ["Legal", "Product", "Engineering"]),
    "financial market regulation": (
        [r"finma", r"geldwäscherei", r"blanchiment", r"riciclaggio", r"anti-money", r"\bGwG\b", r"bank",
         r"finanzmarkt", r"finanzinstitut", r"versicherungsaufsicht", r"wirtschaftlich berechtigt"],
        ["finma_supervised"], ["Compliance", "Legal", "Finance"]),
    "corporate transparency": (
        [r"transparenz juristischer personen", r"wirtschaftlich berechtigten", r"handelsregister", r"aktienrecht"],
        [], ["Legal", "Management", "Finance"]),
    "tax": (
        [r"steuer", r"impôt", r"imposta", r"mehrwertsteuer", r"\bMWST\b", r"\btax\b", r"quellensteuer"],
        [], ["Tax", "Finance"]),
    "health": (
        [r"gesundheit", r"kranken", r"heilmittel", r"medizin", r"prämienregion", r"santé", r"health",
         r"patient", r"transplant", r"epidemie"],
        ["handles_health_data"], ["Legal", "Compliance", "Product"]),
    "employment": (
        [r"arbeitsgesetz", r"arbeitnehm", r"(?<!zusammen)arbeit\b", r"employ", r"travail", r"lavoro", r"sozialversicherung",
         r"\bAHV\b", r"berufliche vorsorge", r"monitoring"],
        ["monitors_employees"], ["HR", "Legal"]),
    "product safety & trade": (
        [r"produktesicherheit", r"handelshemmnis", r"sécurité des produits", r"product safety", r"konsumenten",
         r"konsumentinnen", r"zoll", r"e-commerce", r"fernabsatz"],
        ["sells_physical_products"], ["Product", "Legal", "Operations"]),
    "consumer protection & marketing": (
        [r"lauterer wettbewerb", r"\bUWG\b", r"consent", r"einwilligung", r"werbung", r"marketing", r"dark pattern"],
        ["customer_profiling"], ["Marketing", "Legal", "Product"]),
    "children & minors": (
        [r"kinder", r"jugend", r"minderjährig", r"minors", r"children", r"enfants", r"mineur"],
        ["minors_as_users"], ["Trust & Safety", "Product", "Legal"]),
    "cybersecurity": (
        [r"informationssicherheit", r"cyber", r"sicherheitslücke", r"meldepflicht", r"security"],
        ["processes_personal_data"], ["Security", "Engineering", "Legal"]),
    "foreign investment & sanctions": (
        [r"ausländischer investitionen", r"sanktion", r"embargo", r"investment screening"],
        [], ["Legal", "Management", "Strategy"]),
    "accessibility": (
        [r"barrierefrei", r"behindertengleichstellung", r"accessib", r"accessibilité"],
        ["public_sector_clients"], ["Product", "Design", "Public Affairs"]),
    "nonprofit & social services": (
        [r"nonprofit", r"gemeinnützig", r"beneficiar", r"donor", r"fundrais", r"ngo"],
        ["nonprofit"], ["Legal", "Data", "Fundraising"]),
}


# Almost every client has these, so on their own they are weak evidence.
GENERIC_FLAGS = {"processes_personal_data"}
# Updates triggering these only matter to companies in that sector - unless the update also has
# a general applicability scope (e.g. the beneficial-owner register: AML-motivated, but binding on every AG).
SECTOR_FLAGS = {"finma_supervised", "handles_health_data", "nonprofit", "public_sector_clients", "minors_as_users"}

# Mock classifier: taxonomy topics that are cross-cutting federal law -> applicability scope.
SCOPE_BY_TOPIC = {
    "tax": ["all_legal_entities"],
    "corporate transparency": ["all_legal_entities"],
    "employment": ["employers"],
}
SCOPE_WEIGHT = 0.4  # alone enough to reach the LLM (and to match in mock mode)


def keyword_scan(text: str) -> dict[str, list[str]]:
    """Return {topic: [matched keywords]} for every taxonomy topic found in text."""
    hits: dict[str, list[str]] = {}
    for topic, (patterns, _, _) in TAXONOMY.items():
        # acronyms like \bAI\b / \bKI\b are case-sensitive ("ai" is an Italian word)
        found = [p for p in patterns if re.search(p, text, 0 if re.search(r"[A-Z]{2}", p) else re.I)]
        if found:
            hits[topic] = found
    return hits


def company_scopes(company: dict) -> dict[str, str]:
    """Applicability scopes a company falls into, derived from its profile -> {scope: why}."""
    out = {"all_legal_entities": "every client is a company"}
    has_hr = any("HR" in d.get("functions", []) for d in company.get("departments", []))
    if company.get("size_band") != "1-10" or has_hr or (company.get("flags") or {}).get("monitors_employees"):
        out["employers"] = f"company has staff (size {company.get('size_band')})"
    return out


def profile_rules(company: dict, update: dict, classification: dict | None) -> list[dict]:
    """Compare update metadata/classification with a company profile -> list of RuleHit dicts."""
    hits: list[dict] = []
    cls = classification or {}
    flags = {k for k, v in (company.get("flags") or {}).items() if v}
    triggered = set(cls.get("triggered_flags", []))
    jur = update.get("jurisdiction", "CH")

    for flag in triggered:
        if flag in flags:
            w = 0.2 if flag in GENERIC_FLAGS else 0.5
            hits.append({"rule": f"flag:{flag}", "detail": f"Update concerns '{flag}', which the company declared.", "weight": w})

    # General applicability (every legal entity / every employer). Only for law that binds the company:
    # Swiss law, or foreign law in a jurisdiction the company is active in.
    scopes = {}
    if jur == "CH" or jur in company.get("jurisdictions", []):
        own = company_scopes(company)
        scopes = {s: own[s] for s in cls.get("applies_to", []) if s in own}
    for s, why in scopes.items():
        hits.append({"rule": f"scope:{s}", "detail": f"Update applies to {APPLICABILITY_SCOPES[s].split(' (')[0]}; "
                     f"this company is one ({why}).", "weight": SCOPE_WEIGHT})

    sector = triggered & SECTOR_FLAGS
    if sector and not (sector & flags):
        if scopes:
            hits.append({"rule": "sector:general-scope", "detail": f"Sector-specific parts ({', '.join(sorted(sector))}) "
                         "do not apply, but the update also applies generally (see scope).", "weight": 0.0})
        else:
            hits.append({"rule": "sector:mismatch", "detail": f"Sector-specific update ({', '.join(sorted(sector))}); "
                         "the company is not in that sector.", "weight": -1.0})

    interests = {t.lower() for t in company.get("topics", [])}
    for topic in cls.get("topics", []):
        t = topic.lower()
        if any(t in i or i in t for i in interests):
            hits.append({"rule": f"topic:{topic}", "detail": f"Topic '{topic}' is in the company's topics of interest.", "weight": 0.4})

    haystack = " ".join([company.get("industry", ""), company.get("description", ""),
                         company.get("legal_context", ""), company.get("key_challenges", "")]).lower()
    for bt in cls.get("affected_business_types", []):
        phrase = bt.lower().strip().removesuffix("s")  # "HealthTech", "E-commerce", "B2C platform"
        if len(phrase) > 3 and phrase in haystack:
            hits.append({"rule": f"business_type:{bt}", "detail": f"Company description mentions '{bt}'.", "weight": 0.3})

    if jur == "EU" and "EU" not in company.get("jurisdictions", []):
        hits.append({"rule": "jurisdiction:EU-not-active", "detail": "EU update, but company is not active in the EU.", "weight": -0.4})
    return hits


def score(hits: list[dict]) -> float:
    return max(0.0, min(1.0, sum(h["weight"] for h in hits)))


# ---------------------------------------------------------------- deadline-based urgency

URGENCY_RANK = {"low": 0, "medium": 1, "high": 2}
HIGH_WITHIN_DAYS = 30     # binding change in force within a month (or already in force) -> high
MEDIUM_WITHIN_DAYS = 90   # ... within a quarter -> at least medium
CONSULTATION_MEDIUM_DAYS = 30  # consultation closes soon -> at least medium (taking part is optional)
RECENTLY_IN_FORCE_DAYS = 90    # "already in force" only counts if it happened recently


def _to_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def deadline_urgency(update: dict, today: date) -> tuple[str | None, str]:
    """Minimum urgency implied by the update's dates alone -> (floor or None, reason)."""
    eif = _to_date(update.get("entry_into_force_date"))
    if eif and update.get("update_type") != "consultation":
        days = (eif - today).days
        if -RECENTLY_IN_FORCE_DAYS <= days < 0:
            return "high", f"already in force since {eif.isoformat()}"
        if 0 <= days <= HIGH_WITHIN_DAYS:
            return "high", f"enters into force in {days} days ({eif.isoformat()})"
        if HIGH_WITHIN_DAYS < days <= MEDIUM_WITHIN_DAYS:
            return "medium", f"enters into force in {days} days ({eif.isoformat()})"
    deadline = _to_date(update.get("consultation_deadline"))
    if deadline and 0 <= (deadline - today).days <= CONSULTATION_MEDIUM_DAYS:
        return "medium", f"consultation closes in {(deadline - today).days} days ({deadline.isoformat()})"
    return None, ""


def apply_deadline_floor(urgency: str, update: dict, today: date) -> tuple[str, str | None]:
    """Raise (never lower) urgency to the deadline floor -> (urgency, note if raised)."""
    floor, reason = deadline_urgency(update, today)
    if floor and URGENCY_RANK[floor] > URGENCY_RANK.get(urgency, 1):
        return floor, f"Urgency raised from {urgency} to {floor}: {reason}."
    return urgency, None
