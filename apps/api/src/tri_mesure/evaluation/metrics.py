"""Evaluation metrics: per-category P/R/F1, confusion matrix, per-field P/R/F1."""

import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from tri_mesure.domain.schemas import FIELD_NAMES
from tri_mesure.domain.taxonomy import CATEGORIES


def _norm(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def field_match(name: str, expected: Any, predicted: Any) -> bool:
    if expected is None or predicted is None:
        return expected is predicted
    if name == "adresse_sinistre":
        e, p = _norm(expected), _norm(predicted)
        return bool(e) and bool(p) and (e in p or p in e)
    return bool(_norm(expected) == _norm(predicted))


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class EvalReport:
    n: int = 0
    category: dict[str, PRF] = field(default_factory=lambda: {c: PRF() for c in CATEGORIES})
    confusion: dict[str, dict[str, int]] = field(
        default_factory=lambda: {c: {p: 0 for p in CATEGORIES} for c in CATEGORIES}
    )
    fields: dict[str, PRF] = field(default_factory=lambda: {f: PRF() for f in FIELD_NAMES})
    sender_correct: int = 0
    schema_valid: int = 0
    fallbacks: int = 0
    manual: int = 0
    cost_eur: float = 0.0
    latencies_ms: list[int] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        expected: dict[str, Any],
        predicted_category: str,
        predicted_sender: str,
        predicted_fields: dict[str, Any],
    ) -> None:
        self.n += 1
        exp_cat = expected["category"]
        self.confusion[exp_cat][predicted_category] += 1
        if exp_cat == predicted_category:
            self.category[exp_cat].tp += 1
        else:
            self.category[exp_cat].fn += 1
            self.category[predicted_category].fp += 1
        if expected["sender_type"] == predicted_sender:
            self.sender_correct += 1
        exp_fields = expected.get("fields", {})
        for name in FIELD_NAMES:
            e, p = exp_fields.get(name), predicted_fields.get(name)
            if e is None and p is None:
                continue
            if field_match(name, e, p):
                self.fields[name].tp += 1
            else:
                if p is not None:
                    self.fields[name].fp += 1
                if e is not None:
                    self.fields[name].fn += 1

    @property
    def accuracy(self) -> float:
        return sum(m.tp for m in self.category.values()) / self.n if self.n else 0.0

    @property
    def macro_f1(self) -> float:
        present = [m for m in self.category.values() if m.tp + m.fn > 0]
        return sum(m.f1 for m in present) / len(present) if present else 0.0

    @property
    def field_micro_f1(self) -> float:
        total = PRF(
            sum(m.tp for m in self.fields.values()),
            sum(m.fp for m in self.fields.values()),
            sum(m.fn for m in self.fields.values()),
        )
        return total.f1

    def latency(self, q: float) -> int:
        if not self.latencies_ms:
            return 0
        if len(self.latencies_ms) == 1:
            return self.latencies_ms[0]
        return int(statistics.quantiles(self.latencies_ms, n=100, method="inclusive")[int(q) - 1])

    def summary(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "field_micro_f1": round(self.field_micro_f1, 4),
            "sender_accuracy": round(self.sender_correct / self.n, 4) if self.n else 0.0,
            "schema_valid_rate": round(self.schema_valid / self.n, 4) if self.n else 0.0,
            "fallback_rate": round(self.fallbacks / self.n, 4) if self.n else 0.0,
            "manual_rate": round(self.manual / self.n, 4) if self.n else 0.0,
            "cost_eur_total": round(self.cost_eur, 6),
            "cost_eur_per_email": round(self.cost_eur / self.n, 6) if self.n else 0.0,
            "latency_p50_ms": self.latency(50),
            "latency_p95_ms": self.latency(95),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "per_category": {c: m.as_dict() for c, m in self.category.items()},
            "per_field": {f: m.as_dict() for f, m in self.fields.items()},
            "confusion": self.confusion,
            "errors": self.errors[:50],
        }
