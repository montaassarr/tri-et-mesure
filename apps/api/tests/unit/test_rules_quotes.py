"""Evidence quotes from the rules fallback never cut a word (they are highlighted as is)."""

from tri_mesure.llm.rules_provider import _around
from tri_mesure.pipeline import readable_summary

TEXT = (
    "Votre refus d'indemnisation est inacceptable, "
    "mon contrat CT47962005 prévoit bien cette garantie."
)


def test_quote_snaps_to_whole_words() -> None:
    start = TEXT.index("CT47962005")
    quote = _around(TEXT, start, start + len("CT47962005"), 15)
    assert "CT47962005" in quote
    assert TEXT.find(quote) >= 0
    before = TEXT[TEXT.find(quote) - 1]
    after_i = TEXT.find(quote) + len(quote)
    assert before.isspace()
    assert after_i == len(TEXT) or TEXT[after_i].isspace()


def test_quote_without_whitespace_keeps_the_match() -> None:
    word = "abcdefghijklmnopqrstuvwxyz"
    assert _around(word, 10, 12, 5) == "kl"


def test_summary_is_unmasked_only_while_the_original_exists() -> None:
    body = "Mon contrat CT47962005 ne couvre pas ?"
    masked = "Réclamation. Mon contrat <CONTRAT_1> ne couvre pas ?"
    assert "CT47962005" in readable_summary(masked, "Objet", body)
    assert readable_summary(masked, "Objet", None) == masked
