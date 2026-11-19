from datetime import date

from tri_mesure.llm.rules_provider import classify

RECEIVED = date(2026, 11, 18)


def test_water_damage_with_active_leak() -> None:
    e = classify(
        "Bonjour, je souhaite déclarer un dégât des eaux survenu hier au 12 rue des Lilas, "
        "75011 Paris. L'eau coule encore. Contrat <CONTRAT_1>.",
        RECEIVED,
    )
    assert e.category == "declaration_sinistre"
    assert e.fields.type_dommage == "degat_des_eaux"
    assert e.fields.fuite_active is True
    assert e.fields.date_sinistre == "2026-11-17"
    assert e.fields.numero_contrat == "<CONTRAT_1>"


def test_phishing_doubt() -> None:
    e = classify(
        "J'ai reçu un SMS avec un lien. Est-ce que ce message vient vraiment de vous ?", RECEIVED
    )
    assert e.category == "verification_authenticite"


def test_deadline_is_not_taken_as_claim_date() -> None:
    e = classify(
        "Je vous relance, toujours sans nouvelles. L'artisan commence avant le 25 novembre.",
        RECEIVED,
    )
    assert e.fields.echeance == "2026-11-25"
    assert e.fields.date_sinistre is None


def test_evidence_only_for_filled_fields() -> None:
    e = classify("Bonjour, quels sont les horaires de l'agence ?", RECEIVED)
    filled = {k for k, v in e.fields.model_dump().items() if v is not None}
    assert {ev.field for ev in e.evidence} <= filled
