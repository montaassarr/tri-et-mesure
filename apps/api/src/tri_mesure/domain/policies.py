"""Simulated policy register ("référentiel contrats").

Real claims screens show the contract and its coverage next to the customer's message, so
the handler never has to switch systems. This prototype has no policy system, so it derives
a fictitious but stable contract from the contract number. Clearly labelled as simulated.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta

HOME = {
    "Essentielle": ["degat_des_eaux", "incendie", "tempete", "catastrophe_naturelle"],
    "Confort": ["degat_des_eaux", "incendie", "tempete", "catastrophe_naturelle", "vol", "grele"],
    "Intégrale": [
        "degat_des_eaux",
        "incendie",
        "tempete",
        "catastrophe_naturelle",
        "vol",
        "grele",
        "bris_de_glace",
        "relogement",
    ],
}
AUTO = {
    "Tiers": ["accident_auto"],
    "Tiers plus": ["accident_auto", "bris_de_glace", "vol", "incendie"],
    "Tous risques": [
        "accident_auto",
        "bris_de_glace",
        "vol",
        "incendie",
        "grele",
        "catastrophe_naturelle",
    ],
}
GUARANTEE_LABELS = {
    "degat_des_eaux": "Dégâts des eaux",
    "incendie": "Incendie",
    "tempete": "Tempête",
    "catastrophe_naturelle": "Catastrophes naturelles",
    "vol": "Vol",
    "grele": "Grêle",
    "bris_de_glace": "Bris de glace",
    "relogement": "Relogement d'urgence",
    "accident_auto": "Dommages accident",
}


@dataclass(frozen=True)
class Policy:
    number: str
    product: str
    formula: str
    status: str
    since: date
    deductible_eur: int
    guarantees: dict[str, bool] = field(default_factory=dict)
    simulated: bool = True

    def covers(self, damage: str | None) -> bool | None:
        if damage is None or damage not in self.guarantees:
            return None
        return self.guarantees[damage]


def lookup(number: str | None, vehicle: bool) -> Policy | None:
    if not number:
        return None
    h = int(hashlib.sha256(number.encode()).hexdigest(), 16)
    table = AUTO if vehicle else HOME
    formula = list(table)[h % len(table)]
    included = set(table[formula])
    universe = {g for f in table.values() for g in f}
    return Policy(
        number=number,
        product="Automobile" if vehicle else "Multirisque habitation",
        formula=formula,
        status="actif",
        since=date(2026, 1, 1) - timedelta(days=(h >> 8) % 2000),
        deductible_eur=[0, 150, 300][(h >> 16) % 3],
        guarantees={g: g in included for g in sorted(universe)},
    )
