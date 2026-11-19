"""Deterministic priority rules.

Priority is never asked of the LLM: it is computed from the extracted fields with rules a
handler can read, so every priority comes with its reasons.
"""

from dataclasses import dataclass, field
from datetime import date

from tri_mesure.domain.schemas import ExtractedFields
from tri_mesure.domain.taxonomy import PRIORITY_ORDER, Priority

DEADLINE_SOON_DAYS = 7


@dataclass(frozen=True)
class PriorityResult:
    priority: Priority
    reasons: list[str] = field(default_factory=list)


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def compute_priority(category: str, fields: ExtractedFields, received: date) -> PriorityResult:
    """Return the highest priority triggered by any rule, with every reason that applies."""
    hits: list[tuple[Priority, str]] = []

    if fields.besoin_relogement:
        hits.append(("urgente", "Besoin de relogement signalé"))
    if fields.fuite_active:
        hits.append(("urgente", "Fuite toujours active"))
    if fields.personne_vulnerable:
        hits.append(("urgente", "Personne vulnérable concernée"))

    if category == "demande_avance_relogement":
        hits.append(("haute", "Demande d'avance ou de relogement"))
    if category == "reclamation":
        hits.append(("haute", "Réclamation (risque de saisine du médiateur)"))
    if category == "verification_authenticite":
        hits.append(("haute", "Doute sur un message frauduleux (hameçonnage possible)"))

    deadline = _parse_iso(fields.echeance)
    if deadline is not None:
        days = (deadline - received).days
        if 0 <= days <= DEADLINE_SOON_DAYS:
            hits.append(("haute", f"Échéance dans {days} jour(s)"))
        elif days < 0:
            hits.append(("haute", "Échéance déjà dépassée"))

    if category == "autre" and not hits:
        return PriorityResult("basse", ["Aucun critère d'urgence ; catégorie « autre »"])

    if not hits:
        return PriorityResult("normale", ["Aucun critère d'urgence"])

    best = min(hits, key=lambda h: PRIORITY_ORDER[h[0]])[0]
    reasons = [reason for prio, reason in hits if prio == best] + [
        reason for prio, reason in hits if prio != best
    ]
    return PriorityResult(best, reasons)
