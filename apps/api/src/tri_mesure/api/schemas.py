"""Request and response models (these drive the OpenAPI spec and the typed web client)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from tri_mesure.domain.schemas import Extraction

Verdict = Literal["accepted", "edited", "rejected", "manual_entry"]
RoleCode = Literal["gestionnaire", "responsable", "auditeur", "equipe_ia"]


# --- auth ----------------------------------------------------------------------------


class RoleOut(BaseModel):
    code: str
    label: str
    mission: str
    permissions: list[str]
    home: str


class LoginIn(BaseModel):
    name: str = Field(min_length=2, max_length=40, pattern=r"^[\w .'-]+$")
    role: RoleCode


class UserOut(BaseModel):
    name: str
    role: str
    role_label: str
    permissions: list[str]
    home: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserOut


# --- cases ---------------------------------------------------------------------------


class Span(BaseModel):
    field: str
    quote: str
    start: int | None
    end: int | None


class SlaOut(BaseModel):
    state: Literal["ok", "bientot", "en_retard", "termine"]
    target_hours: int
    due_at: datetime
    minutes_left: int


class SuggestionOut(BaseModel):
    id: int
    created_at: datetime
    source: str = Field(description="AI system that produced it: 'interne' or a vendor code")
    latency_ms: int | None
    provider: str
    model: str
    prompt_version: str
    category: str
    sender_type: str
    confidence: float
    fields: dict[str, Any]
    spans: list[Span]
    summary: str
    priority: str
    priority_reasons: list[str]
    needs_manual: bool
    manual_reason: str | None
    used_fallback: bool
    cost_eur: float


class QueueItem(BaseModel):
    id: int
    subject: str
    sender_email: str
    queued_at: datetime
    arm: Literal["ai", "control"]
    status: Literal["nouveau", "traite", "manuel"]
    analysis_status: Literal["pending", "running", "done", "failed"]
    category: str | None = Field(description="Null when hidden (control arm) or not analysed")
    priority: str | None
    priority_reasons: list[str]
    needs_check: bool = Field(description="Low confidence or model fallback: look carefully")
    sla: SlaOut
    holder: str | None = Field(description="Handler currently holding the case, if any")
    event_id: int | None = Field(description="Climate event this e-mail belongs to, if any")


class LLMCallOut(BaseModel):
    id: int
    created_at: datetime
    provider: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_eur: float | None
    latency_ms: int
    schema_valid: bool
    stop_reason: str | None
    error: str | None
    masked_prompt: str | None


class ReviewOut(BaseModel):
    id: int
    created_at: datetime
    reviewer: str
    reviewer_role: str
    arm: str
    category: str
    fields: dict[str, Any]
    verdicts: dict[str, str]
    diff: dict[str, Any]
    reason_code: str | None
    manual: bool
    seconds_to_decision: float


class CaseDetail(BaseModel):
    id: int
    received_at: datetime
    queued_at: datetime
    closed_at: datetime | None
    sender_email: str
    subject: str
    body: str | None = Field(description="Original text; null once purged after retention.")
    subject_masked: str
    body_masked: str
    pii_counts: dict[str, int]
    arm: Literal["ai", "control"]
    status: Literal["nouveau", "traite", "manuel"]
    analysis_status: Literal["pending", "running", "done", "failed"]
    analysis_error: str | None
    sla: SlaOut
    holder: str | None
    suggestion: SuggestionOut | None = Field(
        description="Hidden (null) for the control arm until the case is closed."
    )
    llm_calls: list[LLMCallOut]
    reviews: list[ReviewOut]


class FieldDecisionIn(BaseModel):
    verdict: Verdict
    value: Any = None


class ReviewIn(BaseModel):
    category: FieldDecisionIn
    fields: dict[str, FieldDecisionIn] = Field(default_factory=dict)
    reason_code: str | None = None
    manual: bool = False
    seconds_to_decision: float = Field(ge=0, le=3600)

    @model_validator(mode="after")
    def reason_required_on_reject(self) -> "ReviewIn":
        rejected = self.category.verdict == "rejected" or any(
            d.verdict == "rejected" for d in self.fields.values()
        )
        if rejected and not self.reason_code:
            raise ValueError("un motif est obligatoire quand une proposition est rejetée")
        return self


class NextCaseOut(BaseModel):
    id: int | None


class SeedOut(BaseModel):
    created: int
    skipped: int
    queued_for_analysis: int


# --- audit ---------------------------------------------------------------------------


class AuditEventOut(BaseModel):
    seq: int
    ts: str
    actor: str
    type: str
    email_id: int | None
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class ChainReportOut(BaseModel):
    ok: bool
    checked: int
    first_broken_seq: int | None
    reason: str | None


# --- measurement & AI ----------------------------------------------------------------


class AssumptionOut(BaseModel):
    key: str
    label: str
    value: float
    unit: str


class AssumptionUpdate(BaseModel):
    value: float = Field(ge=0)


class EvalRunIn(BaseModel):
    provider: Literal["rules", "anthropic", "openai_compat"] = "rules"
    model: str | None = None
    dataset: Literal["ci", "dev", "test"] = "ci"
    prompt_version: str = "v1"


class EvalRunOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    provider: str
    model: str
    prompt_version: str
    dataset: str
    summary: dict[str, Any]
    report: dict[str, Any]
    error: str | None


class AIConfigOut(BaseModel):
    provider: str
    model: str
    prompt_version: str
    daily_budget_eur: float
    spent_today_eur: float
    overridden: bool
    providers_available: dict[str, bool]
    prompt_versions: list[str]
    known_models: dict[str, list[str]]
    prices_usd_per_mtok: dict[str, dict[str, float]]
    queue_depth: int


class AIConfigIn(BaseModel):
    provider: Literal["rules", "anthropic", "openai_compat"]
    model: str | None = Field(default=None, max_length=80)
    prompt_version: str = "v1"


class CountOut(BaseModel):
    count: int


# --- reference data ------------------------------------------------------------------


class FieldGroup(BaseModel):
    label: str
    fields: list[str]


class Meta(BaseModel):
    categories: dict[str, str]
    senders: dict[str, str]
    damages: dict[str, str]
    fields: dict[str, str]
    field_groups: list[FieldGroup]
    reason_codes: dict[str, str]
    sla_targets_hours: dict[str, int]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    worker: Literal["running", "stopped", "disabled"]
    worker_error: str | None = None
    version: str


# --- control tower: external AI sources ---------------------------------------------


class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class SourceUpdate(BaseModel):
    active: bool


class SourceCreated(BaseModel):
    code: str
    name: str
    api_key: str = Field(description="Shown once. Only its SHA-256 is stored.")


class ChampionIn(BaseModel):
    source: str = Field(max_length=40)


class IngestCase(BaseModel):
    """What an external vendor receives: masked text only, never identities."""

    id: int
    received_at: datetime
    subject: str
    body: str


class ExternalSuggestionIn(Extraction):
    """The same contract as our own model output, plus what the vendor knows about itself."""

    model: str = Field(default="inconnu", max_length=80)
    cost_eur: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)


class ExternalSuggestionOut(BaseModel):
    suggestion_id: int
    mode: Literal["champion", "shadow"]


class AlertOut(BaseModel):
    code: str
    severity: Literal["critique", "attention", "info"]
    title: str
    detail: str
    action: str


# --- storm mode ----------------------------------------------------------------------


class CrisisIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    kind: Literal["grele", "tempete", "inondation"]
    volume: int = Field(ge=1, le=400)


# --- handler workspace context ----------------------------------------------------------


class PlaybookStepOut(BaseModel):
    label: str
    why: str
    deadline: str | None
    urgent: bool


class FrameOut(BaseModel):
    name: str
    summary: str
    deadlines: list[str]


class PlaybookOut(BaseModel):
    steps: list[PlaybookStepOut]
    frames: list[FrameOut]
    reply_subject: str
    reply_body: str


class GuaranteeOut(BaseModel):
    code: str
    label: str
    included: bool


class PolicyOut(BaseModel):
    number: str
    product: str
    formula: str
    status: str
    since: str
    deductible_eur: int
    guarantees: list[GuaranteeOut]
    covers_damage: bool | None = Field(
        description="Whether the guarantee for the damage asked about is included (null: n/a)"
    )
    simulated: bool = True


class RelatedCase(BaseModel):
    id: int
    subject: str
    status: str
    queued_at: datetime
    category: str | None
    same_sender: bool


class TimelineEvent(BaseModel):
    seq: int
    ts: str
    actor: str
    type: str
    payload: dict[str, Any]
