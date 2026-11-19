"""Mask personal data before any model call, with reversible placeholders.

Recognisers are regular expressions plus two light heuristics for names (civility + name,
and the signature line after a closing formula). This is deliberately simple and auditable;
a production system would add an NER model (e.g. Presidio with a French spaCy model).
Known limitation: postal addresses are not masked.

The same value always maps to the same placeholder within one e-mail, so the model can
still reason about "the same contract" and extracted tokens can be mapped back server-side.
"""

import re
from dataclasses import dataclass, field

_UPPER = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ"
_NAME_WORD = rf"[{_UPPER}][a-zà-ÿ'’-]+(?:-[{_UPPER}][a-zà-ÿ'’-]+)?"
_NAME = rf"{_NAME_WORD}(?:\s+(?:{_NAME_WORD}|[{_UPPER}]{{2,}}))" + r"{0,2}"

# Order matters only for documentation; overlaps are resolved by position and length.
PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    "IBAN": re.compile(r"\bFR\d{2}(?:\s?[0-9A-Z]{4}){5}\s?[0-9A-Z]{3}\b"),
    "NIR": re.compile(
        r"\b[12]\s?\d{2}\s?(?:0[1-9]|1[0-2])\s?(?:2[AB]|\d{2})\s?\d{3}\s?\d{3}(?:\s?\d{2})\b"
    ),
    "TELEPHONE": re.compile(r"(?<![\w+])(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}\b"),
    "PLAQUE": re.compile(r"\b[A-HJ-NP-TV-Z]{2}[- ]?\d{3}[- ]?[A-HJ-NP-TV-Z]{2}\b"),
    "CONTRAT": re.compile(r"\bCT\d{8}\b"),
    "PERSONNE": re.compile(rf"\b(?:M\.|Mme|Mlle|Monsieur|Madame)\s+(?P<name>{_NAME})"),
}

_CLOSINGS = re.compile(
    r"^(?:bien\s+)?(?:cordialement|à vous|salutations(?:\s+distinguées)?|"
    r"bien à vous|merci(?:\s+d'avance)?|bonne journée|sincères salutations)[\s,.!]*$",
    re.IGNORECASE,
)
_SIGNATURE_NAME = re.compile(rf"^\s*(?:{_NAME})\s*$")

_TOKEN = re.compile(r"<([A-Z]+)_(\d+)>")


@dataclass(frozen=True)
class Entity:
    kind: str
    start: int
    end: int
    value: str
    token: str


@dataclass
class MaskResult:
    masked: str
    mapping: dict[str, str] = field(default_factory=dict)  # token -> original value
    entities: list[Entity] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entities:
            out[e.kind] = out.get(e.kind, 0) + 1
        return out


def _signature_names(text: str) -> list[tuple[int, int]]:
    """Spans of a name on the first non-empty line after a closing formula."""
    spans: list[tuple[int, int]] = []
    lines = text.splitlines(keepends=True)
    offset = 0
    expect_name = False
    for line in lines:
        stripped = line.strip()
        if expect_name and stripped:
            m = _SIGNATURE_NAME.match(line)
            if m:
                start = offset + (len(line) - len(line.lstrip()))
                spans.append((start, start + len(stripped)))
            expect_name = False
        elif _CLOSINGS.match(stripped):
            expect_name = True
        offset += len(line)
    return spans


def _candidates(text: str) -> list[tuple[int, int, str, str]]:
    found: list[tuple[int, int, str, str]] = []
    for kind, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            if kind == "PERSONNE":
                start, end = m.span("name")
            else:
                start, end = m.span()
            found.append((start, end, kind, text[start:end]))
    for start, end in _signature_names(text):
        found.append((start, end, "PERSONNE", text[start:end]))
    return found


def mask(text: str) -> MaskResult:
    candidates = _candidates(text)

    # Every further occurrence of a detected name is masked too.
    names = {value for _, _, kind, value in candidates if kind == "PERSONNE"}
    for name in names:
        for m in re.finditer(re.escape(name), text):
            candidates.append((m.start(), m.end(), "PERSONNE", name))

    # Resolve overlaps: earliest start wins, then longest.
    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    chosen: list[tuple[int, int, str, str]] = []
    last_end = -1
    for cand in candidates:
        if cand[0] >= last_end:
            chosen.append(cand)
            last_end = cand[1]

    value_to_token: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}
    result = MaskResult(masked="")
    pieces: list[str] = []
    cursor = 0
    for start, end, kind, value in chosen:
        key = (kind, value)
        if key not in value_to_token:
            counters[kind] = counters.get(kind, 0) + 1
            token = f"<{kind}_{counters[kind]}>"
            value_to_token[key] = token
            result.mapping[token] = value
        token = value_to_token[key]
        result.entities.append(Entity(kind, start, end, value, token))
        pieces.append(text[cursor:start])
        pieces.append(token)
        cursor = end
    pieces.append(text[cursor:])
    result.masked = "".join(pieces)
    return result


def unmask(value: str, mapping: dict[str, str]) -> str:
    """Replace every placeholder in `value` with its original text."""
    return _TOKEN.sub(lambda m: mapping.get(m.group(0), m.group(0)), value)
