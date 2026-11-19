"""Deterministic keyword-and-regex provider.

Three jobs: a free baseline the LLMs must beat on the evaluation page, a fallback so the
demo never breaks (no key, budget exhausted, provider down), and the provider used by the
CI evaluation gate. It reads the *masked* text, like every other provider.
"""

import re
import time
import unicodedata
from datetime import date, timedelta

from tri_mesure.domain.schemas import Evidence, ExtractedFields, Extraction
from tri_mesure.domain.taxonomy import CATEGORY_LABELS
from tri_mesure.llm.base import LLMResult, Prompt, Usage

MODEL = "rules-v1"

MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}

# (category, weight, patterns) — patterns are matched on accent-stripped lowercase text.
CATEGORY_RULES: list[tuple[str, float, list[str]]] = [
    (
        "verification_authenticite",
        3.0,
        [
            r"vient[- ]il vraiment",
            r"vient[- ]elle vraiment",
            r"est[- ]ce bien vous",
            r"arnaque",
            r"frauduleu",
            r"hameconnage",
            r"phishing",
            r"(sms|mail|message|lien) suspect",
            r"vraiment de vous",
            r"est[- ]ce legitime",
            r"tentative d'escroquerie",
        ],
    ),
    (
        "resiliation",
        3.0,
        [
            r"resilier",
            r"resiliation",
            r"mettre fin a (mon|notre) contrat",
            r"loi hamon",
        ],
    ),
    (
        "reclamation",
        2.5,
        [
            r"inadmissible",
            r"scandaleu",
            r"inacceptable",
            r"je conteste",
            r"contester",
            r"mediateur",
            r"reclamation",
            r"mecontent",
            r"pas d'accord avec",
            r"insatisfait",
            r"deplorable",
            r"honteu",
        ],
    ),
    (
        "demande_avance_relogement",
        2.5,
        [
            r"\bavance\b",
            r"\bacompte\b",
            r"prise en charge (de l'|d'un )?(hotel|hebergement)",
            r"frais d'hotel",
            r"relogement",
            r"nous reloger",
        ],
    ),
    (
        "pieces_justificatives",
        1.5,
        [
            r"ci-joint",
            r"vous trouverez",
            r"piece[s]? jointe",
            r"je vous transmets",
            r"je vous adresse",
            r"\bdevis\b",
            r"\bfacture",
            r"constat amiable",
            r"rapport d'expertise",
            r"photos?\b",
        ],
    ),
    (
        "relance_delai",
        2.0,
        [
            r"\brelance",
            r"toujours pas",
            r"sans nouvelle",
            r"sans reponse",
            r"ou en est",
            r"aucune nouvelle",
            r"depuis \w+ semaines",
            r"je me permets de revenir",
        ],
    ),
    (
        "question_garantie",
        2.0,
        [
            r"suis[- ]je couvert",
            r"sommes[- ]nous couverts",
            r"mon contrat (\S+ )?couvre",
            r"est[- ]ce (pris en charge|couvert)",
            r"\bfranchise\b",
            r"\bplafond\b",
            r"quelles? garanties?",
        ],
    ),
    (
        "declaration_sinistre",
        1.5,
        [
            r"declarer",
            r"declaration de sinistre",
            r"degat",
            r"accident",
            r"cambriol",
            r"\bgrele",
            r"tempete",
            r"incendie",
            r"\bfuite\b",
            r"sinistre survenu",
            r"inond",
        ],
    ),
]

DAMAGE_RULES: list[tuple[str, list[str]]] = [
    ("catastrophe_naturelle", [r"catastrophe naturelle", r"secheresse", r"fissure", r"crue"]),
    (
        "degat_des_eaux",
        [
            r"degat des eaux",
            r"\bfuite\b",
            r"infiltration",
            r"canalisation",
            r"chauffe-eau",
            r"inond",
        ],
    ),
    ("incendie", [r"incendie", r"\bfeu\b", r"brule"]),
    ("grele", [r"\bgrele"]),
    ("tempete", [r"tempete", r"coup de vent", r"arbre (est )?tombe", r"toiture arrachee"]),
    ("vol", [r"cambriol", r"\bvol\b", r"vole[es]?\b", r"effraction"]),
    ("bris_de_glace", [r"pare-brise", r"bris de glace", r"vitre (brisee|cassee)"]),
    ("accident_auto", [r"accident", r"collision", r"percute", r"accroche", r"constat amiable"]),
]

TRUE_RELOGEMENT = [
    r"plus habitable",
    r"inhabitable",
    r"dormir a l'hotel",
    r"nous reloger",
    r"besoin d'un relogement",
    r"heberges? chez",
    r"ne pouvons plus (rester|dormir)",
]
FALSE_RELOGEMENT = [r"pas besoin (d'etre reloges?|de relogement)", r"nous pouvons rester"]
TRUE_FUITE = [
    r"fuit toujours",
    r"fuite (est )?toujours",
    r"coule (encore|toujours)",
    r"continue de couler",
    r"l'eau continue",
]
FALSE_FUITE = [
    r"fuite (a ete|est) (reparee|stoppee|arretee)",
    r"plombier a repare",
    r"fuite est maintenant reparee",
]
TRUE_VULNERABLE = [
    r"personne agee",
    r"\b(8\d|9\d) ans\b",
    r"nourrisson",
    r"\bbebe\b",
    r"handicap",
    r"fauteuil roulant",
    r"enceinte",
    r"dialyse",
    r"gravement malade",
]

DEADLINE_CUES = [
    r"avant le",
    r"au plus tard",
    r"rendez-vous",
    r"passage de l'expert",
    r"visite de l'expert",
    r"date limite",
    r"expire le",
    r"jusqu'au",
]

ADDRESS_RE = re.compile(
    r"\b\d{1,4}(?:\s?(?:bis|ter))?,?\s(?:rue|avenue|boulevard|bd|chemin|allée|impasse|place|"
    r"route|quai|cours|résidence)\s[^\n,.;]{2,60}?"
    r"(?:,?\s\d{5}\s[A-ZÀ-Ü][\w'’ -]{1,40})?(?=[\n,.;)]|$)",
    re.IGNORECASE,
)
DATE_NUM_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
DATE_TXT_RE = re.compile(
    r"\b(\d{1,2})(?:er)?\s(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|"
    r"novembre|decembre)(?:\s(\d{4}))?\b"
)
CONTRACT_RE = re.compile(r"<CONTRAT_\d+>|\bCT\d{8}\b")
PLATE_RE = re.compile(r"<PLAQUE_\d+>")


def _fold(text: str) -> str:
    """Lowercase and strip accents, keeping character positions identical."""
    out = []
    for ch in text.lower():
        decomposed = unicodedata.normalize("NFD", ch)
        base = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
        out.append(base[:1] if base else ch)
    return "".join(out)


def _search(patterns: list[str], folded: str) -> re.Match[str] | None:
    for p in patterns:
        m = re.search(p, folded)
        if m:
            return m
    return None


def _around(original: str, start: int, end: int, pad: int) -> str:
    """The matched text plus up to `pad` characters of context, in whole words only.

    A quote that cuts a word ("e, mon contrat … bien c") is hard to read and makes the
    highlight in the e-mail look wrong, so the window snaps to whitespace on both sides.
    """
    lo = max(0, start - pad)
    hi = min(len(original), end + pad)
    if lo > 0 and not original[lo - 1].isspace():
        gap = re.search(r"\s", original[lo:start])
        lo = lo + gap.end() if gap else start
    if hi < len(original) and not original[hi].isspace():
        gaps = list(re.finditer(r"\s", original[end:hi]))
        hi = end + gaps[-1].start() if gaps else end
    return original[lo:hi].strip()


def _quote(original: str, m: re.Match[str], pad: int = 25) -> str:
    return _around(original, m.start(), m.end(), pad)


def _resolve_date(day: int, month: int, year: int | None, received: date) -> date | None:
    try:
        d = date(year if year else received.year, month, day)
    except ValueError:
        return None
    if year is None and d > received + timedelta(days=60):
        d = d.replace(year=d.year - 1)
    return d


def _find_dates(original: str, folded: str, received: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    for m in DATE_NUM_RE.finditer(folded):
        year = int(m.group(3)) if m.group(3) else None
        if year is not None and year < 100:
            year += 2000
        d = _resolve_date(int(m.group(1)), int(m.group(2)), year, received)
        if d:
            found.append((m.start(), d))
    for m in DATE_TXT_RE.finditer(folded):
        year = int(m.group(3)) if m.group(3) else None
        d = _resolve_date(int(m.group(1)), MONTHS[m.group(2)], year, received)
        if d:
            found.append((m.start(), d))
    for word, delta in (("avant-hier", 2), ("hier", 1), ("cette nuit", 0), ("ce matin", 0)):
        for m in re.finditer(rf"\b{word}\b", folded):
            if word == "hier" and folded[max(0, m.start() - 6) : m.start()] == "avant-":
                continue
            found.append((m.start(), received - timedelta(days=delta)))
    return sorted(found)


def _bool_field(
    true_p: list[str], false_p: list[str], folded: str
) -> tuple[bool | None, re.Match[str] | None]:
    neg = _search(false_p, folded)
    if neg:
        return False, neg
    pos = _search(true_p, folded)
    if pos:
        return True, pos
    return None, None


def _received_from_prompt(user: str) -> date:
    m = re.search(r"Date de réception : (\d{4}-\d{2}-\d{2})", user)
    return date.fromisoformat(m.group(1)) if m else date.today()


def _body_from_prompt(user: str) -> str:
    marker = "--- E-MAIL ---"
    return user.split(marker, 1)[1].strip() if marker in user else user


def classify(text: str, received: date) -> Extraction:
    folded = _fold(text)
    evidence: list[Evidence] = []

    scores: dict[str, float] = {}
    for category, weight, patterns in CATEGORY_RULES:
        hits = sum(1 for p in patterns if re.search(p, folded))
        if hits:
            scores[category] = weight * hits
    if scores:
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        category = ranked[0][0]
        top = ranked[0][1]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        confidence = round(min(0.95, max(0.35, 0.5 + 0.5 * (top - second) / (top + second))), 2)
    else:
        category, confidence = "autre", 0.4

    if re.search(r"garage|carrosserie|atelier de reparation", folded):
        sender = "garage"
    elif re.search(r"cabinet d'expertise|en ma qualite d'expert|l'expert soussigne", folded):
        sender = "expert"
    elif re.search(r"agent general|agence |courtier|mon client|notre client", folded):
        sender = "agent"
    else:
        sender = "assure"

    fields = ExtractedFields()

    m_contract = CONTRACT_RE.search(text)
    if m_contract:
        fields.numero_contrat = m_contract.group(0)
        evidence.append(Evidence(field="numero_contrat", quote=_quote(text, m_contract, 15)))
    m_plate = PLATE_RE.search(text)
    if m_plate:
        fields.immatriculation = m_plate.group(0)
        evidence.append(Evidence(field="immatriculation", quote=_quote(text, m_plate, 15)))
    m_addr = ADDRESS_RE.search(text)
    if m_addr:
        fields.adresse_sinistre = m_addr.group(0).strip()
        evidence.append(Evidence(field="adresse_sinistre", quote=m_addr.group(0).strip()))

    for damage, patterns in DAMAGE_RULES:
        m = _search(patterns, folded)
        if m:
            fields.type_dommage = damage  # type: ignore[assignment]
            evidence.append(Evidence(field="type_dommage", quote=_quote(text, m)))
            break

    for name, (tp, fp) in {
        "besoin_relogement": (TRUE_RELOGEMENT, FALSE_RELOGEMENT),
        "fuite_active": (TRUE_FUITE, FALSE_FUITE),
        "personne_vulnerable": (TRUE_VULNERABLE, []),
    }.items():
        value, m = _bool_field(tp, fp, folded)
        if value is not None and m is not None:
            setattr(fields, name, value)
            evidence.append(Evidence(field=name, quote=_quote(text, m)))

    dates = _find_dates(text, folded, received)
    for pos, d in dates:
        window = folded[max(0, pos - 40) : pos]
        is_deadline = any(re.search(cue, window) for cue in DEADLINE_CUES)
        if is_deadline and fields.echeance is None:
            fields.echeance = d.isoformat()
            evidence.append(Evidence(field="echeance", quote=_around(text, pos, pos + 1, 20)))
        elif not is_deadline and fields.date_sinistre is None and d <= received:
            fields.date_sinistre = d.isoformat()
            evidence.append(Evidence(field="date_sinistre", quote=_around(text, pos, pos + 1, 20)))

    first_sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    summary = f"{CATEGORY_LABELS[category]}. {first_sentence[:160]}"

    return Extraction(
        category=category,
        sender_type=sender,
        confidence=confidence,
        fields=fields,
        evidence=evidence,
        summary=summary,
    ).normalise()


class RulesProvider:
    name = "rules"
    model = MODEL

    async def extract(self, prompt: Prompt) -> LLMResult:
        started = time.perf_counter()
        extraction = classify(_body_from_prompt(prompt.user), _received_from_prompt(prompt.user))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResult(self.name, self.model, extraction, Usage(), latency_ms, "end_turn")
