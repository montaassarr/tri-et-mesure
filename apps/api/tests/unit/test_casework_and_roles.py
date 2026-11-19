from datetime import UTC, datetime, timedelta

from tri_mesure.domain.casework import CLAIM_LEASE, can_claim, claim_holder, sla_for
from tri_mesure.domain.roles import ROLES, has_permission

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_urgent_case_is_late_after_four_hours() -> None:
    sla = sla_for("urgente", NOW - timedelta(hours=5), NOW, closed=False)
    assert sla.state == "en_retard"
    assert sla.minutes_left == -60


def test_due_soon_in_last_quarter_of_target() -> None:
    sla = sla_for("haute", NOW - timedelta(hours=20), NOW, closed=False)
    assert sla.state == "bientot"


def test_untriaged_case_gets_standard_target() -> None:
    sla = sla_for(None, NOW, NOW, closed=False)
    assert sla.target_hours == 72
    assert sla.state == "ok"


def test_closed_case_is_done_whatever_the_clock() -> None:
    assert sla_for("urgente", NOW - timedelta(days=3), NOW, closed=True).state == "termine"


def test_claim_lease_expires() -> None:
    assert claim_holder("sophie", NOW - timedelta(minutes=5), NOW) == "sophie"
    assert claim_holder("sophie", NOW - CLAIM_LEASE - timedelta(seconds=1), NOW) is None


def test_cannot_take_a_case_held_by_someone_else() -> None:
    d = can_claim("nouveau", "sophie", NOW, "karim", NOW)
    assert not d.allowed and d.reason is not None and "sophie" in d.reason
    assert can_claim("nouveau", "sophie", NOW, "sophie", NOW).allowed
    assert can_claim("nouveau", None, None, "karim", NOW).allowed
    assert not can_claim("traite", None, None, "karim", NOW).allowed


def test_permission_matrix() -> None:
    assert has_permission("gestionnaire", "cases.review")
    assert not has_permission("responsable", "cases.review")
    assert not has_permission("gestionnaire", "audit.read")
    assert has_permission("auditeur", "audit.read")
    assert has_permission("equipe_ia", "config.write")
    assert not has_permission("inconnu", "cases.read")
    # every role can at least read cases, and has a home page
    assert all("cases.read" in r.permissions and r.home for r in ROLES.values())


def test_empty_or_weak_auth_secret_is_never_used() -> None:
    import pytest
    from pydantic import ValidationError

    from tri_mesure.settings import DEV_AUTH_SECRET, Settings

    assert Settings(auth_secret="").auth_secret == DEV_AUTH_SECRET
    with pytest.raises(ValidationError):
        Settings(auth_secret="too-short")
