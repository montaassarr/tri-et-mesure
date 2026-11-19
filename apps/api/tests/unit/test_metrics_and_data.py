from tri_mesure.datagen.generate import generate
from tri_mesure.domain.taxonomy import CATEGORIES
from tri_mesure.evaluation.metrics import EvalReport, field_match


def test_field_match_normalises_and_handles_addresses() -> None:
    assert field_match("numero_contrat", "CT12345678", " ct12345678 ")
    assert field_match("adresse_sinistre", "12 rue de la Paix, 75002 Paris", "12 rue de la Paix")
    assert not field_match("date_sinistre", "2026-11-10", "2026-11-11")
    assert field_match("fuite_active", None, None)
    assert not field_match("fuite_active", True, None)


def test_report_counts_tp_fp_fn() -> None:
    r = EvalReport()
    r.add(
        {"category": "reclamation", "sender_type": "assure", "fields": {}},
        "reclamation",
        "assure",
        {},
    )
    r.add(
        {"category": "reclamation", "sender_type": "assure", "fields": {}},
        "relance_delai",
        "assure",
        {"echeance": "2026-11-20"},
    )
    assert r.category["reclamation"].tp == 1
    assert r.category["reclamation"].fn == 1
    assert r.category["relance_delai"].fp == 1
    assert r.fields["echeance"].fp == 1
    assert r.accuracy == 0.5


def test_generator_is_deterministic_and_covers_all_categories() -> None:
    a = generate(60, seed=7)
    b = generate(60, seed=7)
    assert [s.body for s in a] == [s.body for s in b]
    assert {s.expected.category for s in a} == set(CATEGORIES)


def test_generated_labels_appear_in_text() -> None:
    for s in generate(100, seed=3):
        f = s.expected.fields
        for key in ("numero_contrat", "immatriculation"):
            if key in f:
                assert f[key] in s.body
