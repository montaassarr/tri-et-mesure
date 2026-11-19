from tri_mesure.domain import playbook, policies
from tri_mesure.domain.schemas import ExtractedFields


def test_human_urgency_comes_first() -> None:
    pb = playbook.build(
        "declaration_sinistre",
        ExtractedFields(type_dommage="degat_des_eaux", besoin_relogement=True, fuite_active=True),
    )
    assert pb.steps[0].urgent and "relogement" in pb.steps[0].label
    assert pb.steps[1].urgent and "eau" in pb.steps[1].label
    assert any("IRSI" in f.name for f in pb.frames)


def test_complaint_has_regulatory_deadlines_and_mediator() -> None:
    pb = playbook.build("reclamation", ExtractedFields(numero_contrat="CT12345678"))
    assert any("ACPR" in f.name for f in pb.frames)
    assert "CT12345678" in pb.reply_body and "Médiateur" in pb.reply_body


def test_phishing_reply_never_asks_for_anything() -> None:
    pb = playbook.build("verification_authenticite", ExtractedFields())
    assert "ne vient pas de nous" in pb.reply_body
    assert pb.steps[0].urgent


def test_every_category_has_a_playbook() -> None:
    from tri_mesure.domain.taxonomy import CATEGORIES

    for c in CATEGORIES:
        pb = playbook.build(c, ExtractedFields())
        assert pb.steps and pb.reply_body.startswith("Madame, Monsieur")


def test_policy_lookup_is_stable_and_labelled_simulated() -> None:
    a = policies.lookup("CT12345678", vehicle=False)
    b = policies.lookup("CT12345678", vehicle=False)
    assert a == b and a is not None and a.simulated
    assert a.product == "Multirisque habitation"
    assert a.covers("degat_des_eaux") is True  # included in every home formula
    assert policies.lookup(None, vehicle=False) is None
    auto = policies.lookup("CT12345678", vehicle=True)
    assert auto is not None and auto.product == "Automobile"
