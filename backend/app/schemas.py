"""THE CONTRACT between workstreams.

These Pydantic models define every JSON shape the API returns/accepts.
frontend/src/types.ts mirrors this file by hand - change both in the same commit
and tell the team (see docs/CONTRACTS.md).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------- vocabularies

UpdateType = Literal["as_publication", "entry_into_force", "consultation", "simulated"]
Urgency = Literal["high", "medium", "low"]
DraftStatus = Literal["pending", "approved", "rejected", "revision_requested"]
Language = Literal["DE", "FR", "EN", "IT"]

# Canonical functional teams. Updates are classified against these (company-independent);
# each company department declares which of these functions it covers, which is how
# a classified update is routed to concrete departments.
FUNCTIONAL_TEAMS = [
    "Legal", "Compliance", "Product", "Engineering", "Data", "Security", "Marketing",
    "Sales", "HR", "Finance", "Tax", "Operations", "Trust & Safety", "Design",
    "Strategy", "Public Affairs", "Fundraising", "Management",
]

# Company activity flags collected at onboarding. Used by the rules layer.
ACTIVITY_FLAGS = {
    "processes_personal_data": "Processes personal data",
    "customer_profiling": "Does customer profiling or analytics",
    "offers_ai_features": "Offers AI features",
    "monitors_employees": "Monitors employees",
    "finma_supervised": "Is FINMA-supervised",
    "handles_health_data": "Handles health data",
    "minors_as_users": "Has minors as users",
    "sells_physical_products": "Sells physical products",
    "public_sector_clients": "Serves public-sector clients",
    "nonprofit": "Is a nonprofit / handles beneficiary data",
}

# Who an update applies to beyond sector flags: obligations that hit every company of a kind.
# Classified per update; the matching side derives them from the profile (rules.company_scopes).
# An update with a scope is never vetoed as "sector-specific" for companies inside that scope.
APPLICABILITY_SCOPES = {
    "all_legal_entities": "every company / legal entity in Switzerland (e.g. company law, beneficial owners, profit tax)",
    "employers": "every company that employs staff (e.g. labour law, social insurance, payroll withholding tax)",
}

SIZE_BANDS = ["1-10", "11-50", "51-250", "251-1000", "1000+"]
CANTONS = [
    "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE", "NW",
    "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH",
]

DISCLAIMER = (
    "This notification was reviewed by LEXR but is not a full legal assessment of your "
    "situation. It is based on the cited official source and an AI-assisted draft. "
    "Please contact LEXR before taking legal decisions."
)
# Same disclaimer in every client language; alerts and emails use the draft's language.
DISCLAIMERS = {
    "EN": DISCLAIMER,
    "DE": ("Diese Mitteilung wurde von LEXR geprüft, ist aber keine vollständige rechtliche Beurteilung Ihrer "
           "Situation. Sie beruht auf der zitierten amtlichen Quelle und einem KI-gestützten Entwurf. "
           "Bitte kontaktieren Sie LEXR, bevor Sie rechtliche Entscheidungen treffen."),
    "FR": ("Cette notification a été vérifiée par LEXR, mais ne constitue pas une analyse juridique complète de votre "
           "situation. Elle repose sur la source officielle citée et sur un projet assisté par IA. "
           "Veuillez contacter LEXR avant de prendre des décisions juridiques."),
    "IT": ("Questa notifica è stata verificata da LEXR, ma non costituisce una valutazione giuridica completa della "
           "vostra situazione. Si basa sulla fonte ufficiale citata e su una bozza assistita dall'IA. "
           "Si prega di contattare LEXR prima di prendere decisioni giuridiche."),
}


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- company profile

class DepartmentIn(BaseModel):
    name: str
    contact_email: str
    functions: list[str] = Field(default_factory=list, description="subset of FUNCTIONAL_TEAMS")
    responsibilities: str = ""


class DepartmentOut(DepartmentIn, ORM):
    id: int


class CompanyIn(BaseModel):
    name: str
    industry: str
    description: str = ""
    size_band: str
    hq_canton: str
    jurisdictions: list[str] = Field(default_factory=lambda: ["CH"])  # "CH", "EU", "other"
    flags: dict[str, bool] = Field(default_factory=dict)  # keys from ACTIVITY_FLAGS
    legal_context: str = ""  # current legal situation, in the client's words
    key_challenges: str = ""
    topics: list[str] = Field(default_factory=list)  # free tags
    preferred_language: Language = "EN"
    departments: list[DepartmentIn] = Field(default_factory=list)


class CompanyOut(CompanyIn, ORM):
    id: int
    departments: list[DepartmentOut]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- regulatory update

class SourceRef(BaseModel):
    source: str  # "fedlex" | "organisers_dataset" | ...
    external_id: str
    url: str | None = None
    version: str | None = None
    fetched_at: str


class SourceArticle(BaseModel):
    ref: str  # e.g. "Art. 3" - what citations point at
    text: str


class Classification(BaseModel):
    """Company-independent classification of an update (AI step 1)."""
    topics: list[str]
    functional_teams: list[str]  # subset of FUNCTIONAL_TEAMS
    triggered_flags: list[str]  # subset of ACTIVITY_FLAGS keys
    affected_business_types: list[str] = Field(default_factory=list)
    applies_to: list[str] = Field(default_factory=list)  # subset of APPLICABILITY_SCOPES keys
    urgency: Urgency
    rationale: str
    model_version: str
    prompt_version: str
    classified_at: str


class RegulatoryUpdateOut(ORM):
    id: str
    dedup_key: str
    eli_uri: str | None
    sr_number: str | None
    title: str
    update_type: UpdateType
    jurisdiction: str
    publication_date: str | None
    entry_into_force_date: str | None
    consultation_deadline: str | None
    source_language: str
    source_text: str | None
    source_articles: list[SourceArticle]
    source_text_url: str | None
    source_url: str | None
    source_version: str | None
    sources: list[SourceRef]
    is_simulated: bool
    metadata_extra: dict
    classification: Classification | None
    fetched_at: datetime


class RegulatoryUpdateListItem(ORM):
    """Light version without the full source text."""
    id: str
    title: str
    update_type: UpdateType
    jurisdiction: str
    eli_uri: str | None
    publication_date: str | None
    entry_into_force_date: str | None
    consultation_deadline: str | None
    source_language: str
    is_simulated: bool
    sources: list[SourceRef]
    classification: Classification | None


# ---------------------------------------------------------------- match

class RuleHit(BaseModel):
    rule: str  # e.g. "flag:finma_supervised", "topic:data protection", "jurisdiction:EU"
    detail: str
    weight: float


class MatchOut(ORM):
    id: int
    update_id: str
    company_id: int
    matched: bool
    relevance_score: float
    rule_hits: list[RuleHit]
    llm_reason: str
    model_version: str
    prompt_version: str
    created_at: datetime


# ---------------------------------------------------------------- draft

class Citation(BaseModel):
    claim: str  # the statement in the draft this citation supports
    eli: str | None  # ELI URI (None only for simulated sources)
    article: str | None  # e.g. "Art. 3 Abs. 2"
    quote: str | None = None  # short verbatim excerpt from the source, original language
    source_url: str | None = None


class AffectedDepartment(BaseModel):
    department_id: int | None
    name: str
    why: str


class NextStep(BaseModel):
    action: str
    department: str | None = None
    due: str | None = None  # ISO date if derivable from the source (e.g. entry into force)


class RevisionEntry(BaseModel):
    version: int
    at: str
    by: str
    change: str  # "generated" | "edited" | "regenerated_after_revision_request"
    snapshot: dict


class ReviewerComment(BaseModel):
    at: str
    by: str
    decision: str
    comment: str


class DraftOut(ORM):
    id: int
    match_id: int
    company_id: int
    update_id: str
    version: int
    summary: str
    affected_departments: list[AffectedDepartment]
    next_steps: list[NextStep]
    urgency: Urgency
    citations: list[Citation]
    status: DraftStatus
    reviewer_comments: list[ReviewerComment]
    revision_history: list[RevisionEntry]
    model_version: str
    prompt_version: str
    # client-facing title and the language the draft is written in (None on drafts from before draft-v2)
    title: str | None = None
    language: Language | None = None
    edited_by_lawyer: bool
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # computed quality flags for the review screen
    warnings: list[str] = Field(default_factory=list)


class DraftDetail(DraftOut):
    """Everything the lawyer review screen needs in one call."""
    update: RegulatoryUpdateOut
    match: MatchOut
    company: CompanyOut


class DraftEdit(BaseModel):
    title: str | None = None
    summary: str | None = None
    affected_departments: list[AffectedDepartment] | None = None
    next_steps: list[NextStep] | None = None
    urgency: Urgency | None = None
    citations: list[Citation] | None = None


class ReviewDecision(BaseModel):
    comment: str = ""


# ---------------------------------------------------------------- alert

class AlertOut(ORM):
    id: int
    draft_id: int
    company_id: int
    departments: list[AffectedDepartment]
    delivered_at: datetime
    reviewed_by: str
    read_at: datetime | None
    # denormalised for the inbox
    title: str
    summary: str
    next_steps: list[NextStep]
    urgency: Urgency
    citations: list[Citation]
    source_url: str | None
    is_simulated: bool
    language: Language = "EN"
    disclaimer: str = DISCLAIMER


class EmailPreview(BaseModel):
    to: list[str]
    subject: str
    body_text: str


# ---------------------------------------------------------------- audit & pipeline

class AuditLogOut(ORM):
    id: int
    timestamp: datetime
    actor: str
    action: str
    object_type: str
    object_id: str
    details: dict


class PipelineResult(BaseModel):
    step: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    info: dict = Field(default_factory=dict)


class Meta(BaseModel):
    functional_teams: list[str] = FUNCTIONAL_TEAMS
    activity_flags: dict[str, str] = ACTIVITY_FLAGS
    size_bands: list[str] = SIZE_BANDS
    cantons: list[str] = CANTONS
    disclaimer: str = DISCLAIMER
    demo_mode: bool
    llm_provider: str
    llm_model: str
