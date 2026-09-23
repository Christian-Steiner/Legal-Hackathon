"""Deterministic layer (workstream 2): keyword taxonomy + profile rules.

Used (a) as the first, transparent matching step before the LLM and
(b) as the whole classifier/matcher when LLM_PROVIDER=mock.
TODO(ws2): extend the taxonomy; tune weights; add rules for jurisdictions/size/canton.
"""
import re

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
        [r"arbeitsgesetz", r"arbeitnehm", r"arbeit\b", r"employ", r"travail", r"lavoro", r"sozialversicherung",
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
# Updates triggering these only matter to companies in that sector.
SECTOR_FLAGS = {"finma_supervised", "handles_health_data", "nonprofit", "public_sector_clients", "minors_as_users"}


def keyword_scan(text: str) -> dict[str, list[str]]:
    """Return {topic: [matched keywords]} for every taxonomy topic found in text."""
    hits: dict[str, list[str]] = {}
    for topic, (patterns, _, _) in TAXONOMY.items():
        # acronyms like \bAI\b / \bKI\b are case-sensitive ("ai" is an Italian word)
        found = [p for p in patterns if re.search(p, text, 0 if re.search(r"[A-Z]{2}", p) else re.I)]
        if found:
            hits[topic] = found
    return hits


def profile_rules(company: dict, update: dict, classification: dict | None) -> list[dict]:
    """Compare update metadata/classification with a company profile -> list of RuleHit dicts."""
    hits: list[dict] = []
    cls = classification or {}
    flags = {k for k, v in (company.get("flags") or {}).items() if v}
    triggered = set(cls.get("triggered_flags", []))

    for flag in triggered:
        if flag in flags:
            w = 0.2 if flag in GENERIC_FLAGS else 0.5
            hits.append({"rule": f"flag:{flag}", "detail": f"Update concerns '{flag}', which the company declared.", "weight": w})

    sector = triggered & SECTOR_FLAGS
    if sector and not (sector & flags):
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

    jur = update.get("jurisdiction", "CH")
    if jur == "EU" and "EU" not in company.get("jurisdictions", []):
        hits.append({"rule": "jurisdiction:EU-not-active", "detail": "EU update, but company is not active in the EU.", "weight": -0.4})

    # Cross-cutting federal law (tax, corporate) touches every Swiss company a little.
    for topic in ("tax", "corporate transparency"):
        if topic in cls.get("topics", []) and jur == "CH":
            hits.append({"rule": f"baseline:{topic}", "detail": "Applies to Swiss companies generally.", "weight": 0.2})
    return hits


def score(hits: list[dict]) -> float:
    return max(0.0, min(1.0, sum(h["weight"] for h in hits)))
