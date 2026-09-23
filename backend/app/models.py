"""SQLAlchemy tables. The JSON shapes exposed by the API live in app/schemas.py (the contract)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    size_band: Mapped[str] = mapped_column(String(20))
    hq_canton: Mapped[str] = mapped_column(String(2))
    jurisdictions: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    legal_context: Mapped[str] = mapped_column(Text, default="")
    key_challenges: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    preferred_language: Mapped[str] = mapped_column(String(2), default="EN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    departments: Mapped[list["Department"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="Department.id"
    )


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(100))
    contact_email: Mapped[str] = mapped_column(String(200))
    functions: Mapped[list] = mapped_column(JSON, default=list)  # canonical teams, see schemas.FUNCTIONAL_TEAMS
    responsibilities: Mapped[str] = mapped_column(Text, default="")

    company: Mapped[Company] = relationship(back_populates="departments")


class RegulatoryUpdate(Base):
    __tablename__ = "regulatory_updates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "fedlex:oc/2026/322", "dataset:R001"
    dedup_key: Mapped[str] = mapped_column(String(200), index=True, unique=True)
    eli_uri: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sr_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    update_type: Mapped[str] = mapped_column(String(30))
    jurisdiction: Mapped[str] = mapped_column(String(10), default="CH")
    publication_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_into_force_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    consultation_deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_language: Mapped[str] = mapped_column(String(2), default="DE")
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_articles: Mapped[list] = mapped_column(JSON, default=list)  # [{ref, text}]
    source_text_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)  # every source that reported this change
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict)
    classification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("update_id", "company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    update_id: Mapped[str] = mapped_column(ForeignKey("regulatory_updates.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    matched: Mapped[bool] = mapped_column(Boolean)
    relevance_score: Mapped[float] = mapped_column(default=0.0)
    rule_hits: Mapped[list] = mapped_column(JSON, default=list)
    llm_reason: Mapped[str] = mapped_column(Text, default="")
    model_version: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    update: Mapped[RegulatoryUpdate] = relationship()
    company: Mapped[Company] = relationship()


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    update_id: Mapped[str] = mapped_column(ForeignKey("regulatory_updates.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text)
    affected_departments: Mapped[list] = mapped_column(JSON, default=list)
    next_steps: Mapped[list] = mapped_column(JSON, default=list)
    urgency: Mapped[str] = mapped_column(String(10))
    citations: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    reviewer_comments: Mapped[list] = mapped_column(JSON, default=list)
    revision_history: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)  # client-facing, in the draft's language
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)  # DE | FR | IT | EN
    edited_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    match: Mapped[Match] = relationship()
    update: Mapped[RegulatoryUpdate] = relationship()
    company: Mapped[Company] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    departments: Mapped[list] = mapped_column(JSON, default=list)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[str] = mapped_column(String(100))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    draft: Mapped[Draft] = relationship()


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(100))  # "system", "model:<name>", "lawyer:<name>", "client:<company>"
    action: Mapped[str] = mapped_column(String(50))
    object_type: Mapped[str] = mapped_column(String(30))
    object_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
