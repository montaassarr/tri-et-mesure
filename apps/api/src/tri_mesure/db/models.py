"""Database schema (SQLAlchemy 2.0 typed mappings).

JSON columns use JSONB on PostgreSQL and plain JSON elsewhere (tests run on SQLite).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Dialect, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator[datetime]):
    """Timestamps are always timezone-aware UTC in Python, whatever the database returns.

    PostgreSQL stores TIMESTAMPTZ; SQLite (tests) returns naive values. Without this,
    comparing a stored time with `datetime.now(UTC)` would raise on one backend only.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime())
    sender_email: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body_raw: Mapped[str | None] = mapped_column(Text)  # purged after the retention period
    body_masked: Mapped[str] = mapped_column(Text)
    subject_masked: Mapped[str] = mapped_column(String(300))
    pii_counts: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    arm: Mapped[str] = mapped_column(String(10), default="ai")  # ai | control
    # Case lifecycle (see domain/casework.py): nouveau -> traite | manuel
    status: Mapped[str] = mapped_column(String(20), default="nouveau", index=True)
    queued_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Work assignment: a handler takes a case for CLAIM_LEASE (lease, not a lock).
    assigned_to: Mapped[str | None] = mapped_column(String(80))
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Asynchronous AI analysis (outbox-style): pending -> running -> done | failed
    analysis_status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0)
    analysis_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    analysis_error: Mapped[str | None] = mapped_column(String(300))
    # Climate event (storm mode) this e-mail belongs to, if any.
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("crisis_events.id", ondelete="SET NULL"), index=True
    )
    # Ground truth, only for synthetic data (used by the pilot to score human decisions).
    gold: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="email", order_by="Suggestion.id", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="email", order_by="Review.id", cascade="all, delete-orphan"
    )


class LLMCall(Base):
    """Cost ledger. Column names follow the OpenTelemetry GenAI semantic conventions."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    # indexed: the daily budget check sums today's costs on every model call
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    purpose: Mapped[str] = mapped_column(String(20), default="suggest")  # suggest | eval
    gen_ai_system: Mapped[str] = mapped_column(String(40))  # provider
    gen_ai_request_model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    gen_ai_usage_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    gen_ai_usage_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_eur: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_reason: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(500))
    masked_prompt: Mapped[str | None] = mapped_column(Text)  # only masked text is ever stored


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    llm_call_id: Mapped[int | None] = mapped_column(ForeignKey("llm_calls.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # Which AI system produced it: "interne" (our pipeline) or an external vendor's code.
    source: Mapped[str] = mapped_column(String(40), default="interne", index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(40))
    sender_type: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONType)
    spans: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    summary: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10))
    priority_reasons: Mapped[list[str]] = mapped_column(JSONType, default=list)
    needs_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_reason: Mapped[str | None] = mapped_column(String(200))
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_eur: Mapped[float] = mapped_column(Float, default=0.0)

    email: Mapped[Email] = relationship(back_populates="suggestions")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique: one closing decision per case, enforced by the database (race-proof)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), unique=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("suggestions.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    reviewer: Mapped[str] = mapped_column(String(80))
    reviewer_role: Mapped[str] = mapped_column(String(20), default="gestionnaire")
    arm: Mapped[str] = mapped_column(String(10))
    # final values chosen by the human
    category: Mapped[str] = mapped_column(String(40))
    fields: Mapped[dict[str, Any]] = mapped_column(JSONType)
    # per item: {"category": "accepted", "numero_contrat": "edited", ...}
    verdicts: Mapped[dict[str, str]] = mapped_column(JSONType, default=dict)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    reason_code: Mapped[str | None] = mapped_column(String(40))
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    seconds_to_decision: Mapped[float] = mapped_column(Float)

    email: Mapped[Email] = relationship(back_populates="reviews")


class AuditEvent(Base):
    """Append-only (enforced by a PostgreSQL trigger) and hash-chained."""

    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    ts: Mapped[str] = mapped_column(String(40))  # ISO-8601 string, exactly as hashed
    actor: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(40))
    # no FK: events outlive purges
    email_id: Mapped[int | None] = mapped_column(Integer, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | error
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    dataset: Mapped[str] = mapped_column(String(40))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    report: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class AISource(Base):
    """An AI system that proposes suggestions: our pipeline, or an external vendor.

    External sources authenticate with an API key (only its SHA-256 is stored) and receive
    masked text only. One source is the champion (shown to handlers); the others run in
    shadow mode and are scored on the same cases.
    """

    __tablename__ = "ai_sources"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))  # internal | external
    api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(80), default="system")


class CrisisEvent(Base):
    """A declared climate event (storm, hail, flood) that floods the queue."""

    __tablename__ = "crisis_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # grele | tempete | inondation
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    volume: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(80))


class AppConfig(Base):
    """Runtime overrides of the AI configuration (provider, model, prompt version).

    Environment variables give the defaults; the AI team can change them at runtime from the
    UI, and every change is written to the audit log.
    """

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_by: Mapped[str] = mapped_column(String(80))


class Assumption(Base):
    __tablename__ = "assumptions"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


DEFAULT_ASSUMPTIONS: list[dict[str, Any]] = [
    {
        "key": "baseline_minutes",
        "label": "Minutes de traitement d'un e-mail sans IA",
        "value": 4.0,
        "unit": "min",
    },
    {
        "key": "monthly_volume",
        "label": "E-mails sinistres reçus par mois (équipe fictive)",
        "value": 20000,
        "unit": "e-mails",
    },
    {
        "key": "cost_per_hour",
        "label": "Coût horaire chargé d'un gestionnaire",
        "value": 35.0,
        "unit": "€/h",
    },
]
