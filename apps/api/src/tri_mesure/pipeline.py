"""E-mail -> masked prompt -> suggestion -> unmasked fields with source spans.

Shared by the API and the evaluation harness so both measure exactly the same path.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from tri_mesure.domain.priority_rules import PriorityResult, compute_priority
from tri_mesure.domain.schemas import ExtractedFields, Extraction
from tri_mesure.domain.taxonomy import MANUAL_REVIEW_CONFIDENCE
from tri_mesure.llm.gateway import Gateway, GatewayOutcome
from tri_mesure.pii.masker import MaskResult, mask, unmask

_SEP = "\n§§§\n"


@dataclass
class MaskedEmail:
    subject: str
    body: str
    result: MaskResult


def mask_email(subject: str, body: str) -> MaskedEmail:
    """Mask subject and body together so one value gets one placeholder in both."""
    result = mask(subject + _SEP + body)
    masked_subject, _, masked_body = result.masked.partition(_SEP)
    return MaskedEmail(masked_subject, masked_body, result)


def unmask_fields(extraction: Extraction, mapping: dict[str, str]) -> dict[str, Any]:
    fields = extraction.fields.model_dump()
    return {k: unmask(v, mapping) if isinstance(v, str) else v for k, v in fields.items()}


def readable_summary(summary: str, subject: str, body: str | None) -> str:
    """The model summarises masked text; show the handler the real values again.

    Done at read time, never stored: once the original is purged (retention), the
    mapping is gone and the masked summary is all that remains — by design.
    """
    if body is None or "<" not in summary:
        return summary
    return unmask(summary, mask_email(subject, body).result.mapping)


def evidence_spans(
    extraction: Extraction, mapping: dict[str, str], original: str
) -> list[dict[str, Any]]:
    """Locate each evidence quote in the original text (after unmasking)."""
    spans: list[dict[str, Any]] = []
    lowered = original.lower()
    for ev in extraction.evidence:
        quote = unmask(ev.quote, mapping).strip()
        if not quote:
            continue
        start = original.find(quote)
        if start < 0:
            start = lowered.find(quote.lower())
        spans.append(
            {
                "field": ev.field,
                "quote": quote,
                "start": start if start >= 0 else None,
                "end": start + len(quote) if start >= 0 else None,
            }
        )
    return spans


@dataclass
class Suggestion:
    masked: MaskedEmail
    outcome: GatewayOutcome
    fields: dict[str, Any]
    spans: list[dict[str, Any]]
    priority: PriorityResult
    needs_manual: bool
    manual_reason: str | None


async def suggest(gateway: Gateway, subject: str, body: str, received: date) -> Suggestion:
    masked = mask_email(subject, body)
    outcome = await gateway.suggest(masked.subject, masked.body, received)
    extraction = outcome.extraction
    assert extraction is not None  # the rules fallback always returns one
    fields = unmask_fields(extraction, masked.result.mapping)
    spans = evidence_spans(extraction, masked.result.mapping, body)

    priority = compute_priority(extraction.category, ExtractedFields(**fields), received)
    manual_reason = outcome.manual_reason
    if manual_reason is None and extraction.confidence < MANUAL_REVIEW_CONFIDENCE:
        manual_reason = f"Confiance faible ({extraction.confidence:.2f})"
    return Suggestion(
        masked, outcome, fields, spans, priority, manual_reason is not None, manual_reason
    )
