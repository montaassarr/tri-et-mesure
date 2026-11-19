from datetime import date

from tri_mesure.domain.priority_rules import compute_priority
from tri_mesure.domain.schemas import ExtractedFields

RECEIVED = date(2026, 11, 18)


def test_no_signal_is_normal() -> None:
    r = compute_priority("declaration_sinistre", ExtractedFields(), RECEIVED)
    assert r.priority == "normale"
    assert r.reasons


def test_active_leak_is_urgent_with_reason() -> None:
    r = compute_priority("declaration_sinistre", ExtractedFields(fuite_active=True), RECEIVED)
    assert r.priority == "urgente"
    assert "Fuite toujours active" in r.reasons


def test_highest_priority_wins_and_all_reasons_are_kept() -> None:
    fields = ExtractedFields(besoin_relogement=True, echeance="2026-11-20")
    r = compute_priority("reclamation", fields, RECEIVED)
    assert r.priority == "urgente"
    assert r.reasons[0] == "Besoin de relogement signalé"
    assert any("Réclamation" in x for x in r.reasons)
    assert any("Échéance dans 2 jour(s)" in x for x in r.reasons)


def test_deadline_far_away_does_not_raise_priority() -> None:
    r = compute_priority("relance_delai", ExtractedFields(echeance="2026-12-30"), RECEIVED)
    assert r.priority == "normale"


def test_past_deadline_is_high() -> None:
    r = compute_priority("relance_delai", ExtractedFields(echeance="2026-11-10"), RECEIVED)
    assert r.priority == "haute"


def test_phishing_doubt_is_high() -> None:
    r = compute_priority("verification_authenticite", ExtractedFields(), RECEIVED)
    assert r.priority == "haute"


def test_other_without_signal_is_low() -> None:
    assert compute_priority("autre", ExtractedFields(), RECEIVED).priority == "basse"


def test_invalid_date_is_ignored() -> None:
    r = compute_priority("relance_delai", ExtractedFields(echeance="bientôt"), RECEIVED)
    assert r.priority == "normale"
