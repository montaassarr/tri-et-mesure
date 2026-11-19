"""Case lifecycle rules: service-level targets and who may work on a case.

Pure functions (no I/O) so the rules are unit-tested and shared by the API and the worker.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

# Target time from arrival in the queue to a closed case, per priority.
SLA_HOURS: dict[str, int] = {"urgente": 4, "haute": 24, "normale": 72, "basse": 120}
# Without AI triage (control arm) there is no priority: every case gets the standard target.
UNTRIAGED_PRIORITY = "normale"
# A case taken by a handler stays reserved for this long without activity.
CLAIM_LEASE = timedelta(minutes=15)
DUE_SOON_FRACTION = 0.25

SlaState = Literal["ok", "bientot", "en_retard", "termine"]
CaseStatus = Literal["nouveau", "traite", "manuel"]
AnalysisStatus = Literal["pending", "running", "done", "failed"]


@dataclass(frozen=True)
class Sla:
    target_hours: int
    due_at: datetime
    state: SlaState
    minutes_left: int  # negative when late


def sla_for(priority: str | None, queued_at: datetime, now: datetime, closed: bool) -> Sla:
    hours = SLA_HOURS.get(priority or UNTRIAGED_PRIORITY, SLA_HOURS[UNTRIAGED_PRIORITY])
    due = queued_at + timedelta(hours=hours)
    minutes_left = int((due - now).total_seconds() // 60)
    if closed:
        state: SlaState = "termine"
    elif minutes_left < 0:
        state = "en_retard"
    elif minutes_left < hours * 60 * DUE_SOON_FRACTION:
        state = "bientot"
    else:
        state = "ok"
    return Sla(hours, due, state, minutes_left)


@dataclass(frozen=True)
class ClaimDecision:
    allowed: bool
    reason: str | None = None


def claim_holder(
    assigned_to: str | None, assigned_at: datetime | None, now: datetime
) -> str | None:
    """Who currently holds the case, or None if free or the lease expired."""
    if assigned_to is None or assigned_at is None:
        return None
    return assigned_to if now - assigned_at < CLAIM_LEASE else None


def can_claim(
    status: str, assigned_to: str | None, assigned_at: datetime | None, user: str, now: datetime
) -> ClaimDecision:
    if status != "nouveau":
        return ClaimDecision(False, "Dossier déjà traité")
    holder = claim_holder(assigned_to, assigned_at, now)
    if holder is not None and holder != user:
        return ClaimDecision(False, f"Dossier pris en charge par {holder}")
    return ClaimDecision(True)
