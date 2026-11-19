from tri_mesure.pii.masker import mask, unmask


def test_masks_each_kind_with_typed_placeholders() -> None:
    text = (
        "Bonjour, contrat CT12345678, véhicule AB-123-CD. Tél : 06 12 34 56 78, "
        "mail jean.dupont@example.fr, IBAN FR76 3000 6000 0112 3456 7890 189."
    )
    result = mask(text)
    assert "<CONTRAT_1>" in result.masked
    assert "<PLAQUE_1>" in result.masked
    assert "<TELEPHONE_1>" in result.masked
    assert "<EMAIL_1>" in result.masked
    assert "<IBAN_1>" in result.masked
    for value in ("CT12345678", "AB-123-CD", "06 12 34 56 78", "jean.dupont@example.fr"):
        assert value not in result.masked


def test_same_value_gets_same_token_and_roundtrips() -> None:
    text = "Contrat CT11112222. Je répète : CT11112222. Autre contrat CT33334444."
    result = mask(text)
    assert result.masked.count("<CONTRAT_1>") == 2
    assert "<CONTRAT_2>" in result.masked
    assert unmask(result.masked, result.mapping) == text


def test_civility_and_signature_names_are_masked_everywhere() -> None:
    text = (
        "Mon client M. Paul Martin attend toujours.\n\n"
        "Cordialement,\nClaire Dubois\nTél : 07 11 22 33 44\n\n"
        "PS : Claire Dubois sera absente lundi."
    )
    result = mask(text)
    assert "Paul Martin" not in result.masked
    assert "Claire Dubois" not in result.masked
    assert result.masked.count("<PERSONNE_2>") == 2


def test_nir_is_masked() -> None:
    result = mask("Mon numéro de sécurité sociale : 1 85 05 78 006 084 36.")
    assert "<NIR_1>" in result.masked


def test_plain_text_is_untouched() -> None:
    text = "La tempête a arraché une partie de la toiture le 20 septembre."
    assert mask(text).masked == text


def test_unmask_leaves_unknown_tokens() -> None:
    assert unmask("<CONTRAT_9>", {}) == "<CONTRAT_9>"
