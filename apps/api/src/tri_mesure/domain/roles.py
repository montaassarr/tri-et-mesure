"""Actors and permissions — the single source of truth (API guards, UI navigation, docs).

Human actors log in with one role. System actors never log in; they appear in the audit log
under their own name so every action has an identified author.
"""

from dataclasses import dataclass
from typing import Literal

Role = Literal["gestionnaire", "responsable", "auditeur", "equipe_ia"]

Permission = Literal[
    "cases.read",  # see the queue and case files
    "cases.review",  # take a case and record a decision
    "pilotage.read",  # team dashboard (aggregates only)
    "assumptions.write",  # edit business assumptions used by estimates
    "audit.read",  # audit log, chain verification, processing register
    "eval.read",  # offline evaluation results and production quality
    "eval.run",  # launch an evaluation (may spend money)
    "config.write",  # change provider / model / prompt version
    "demo.seed",  # load synthetic demo data
    "crisis.manage",  # declare / close a climate event (storm mode)
]


@dataclass(frozen=True)
class RoleInfo:
    label: str
    mission: str
    permissions: frozenset[str]
    home: str


ROLES: dict[str, RoleInfo] = {
    "gestionnaire": RoleInfo(
        label="Gestionnaire sinistres",
        mission="Traite le courrier : vérifie les propositions de l'IA et décide.",
        permissions=frozenset({"cases.read", "cases.review", "demo.seed"}),
        home="/",
    ),
    "responsable": RoleInfo(
        label="Responsable d'équipe",
        mission="Pilote l'activité : stock, délais, valeur réelle de l'IA.",
        permissions=frozenset(
            {"cases.read", "pilotage.read", "assumptions.write", "demo.seed", "crisis.manage"}
        ),
        home="/pilotage",
    ),
    "auditeur": RoleInfo(
        label="Auditeur conformité",
        mission="Contrôle la traçabilité et la protection des données.",
        permissions=frozenset({"cases.read", "audit.read"}),
        home="/journal",
    ),
    "equipe_ia": RoleInfo(
        label="Équipe IA",
        mission="Évalue les modèles, suit la qualité en production, règle la configuration.",
        permissions=frozenset({"cases.read", "eval.read", "eval.run", "config.write", "demo.seed"}),
        home="/ia",
    ),
}

# Actors that act without logging in. Shown in the audit log and the architecture docs.
SYSTEM_ACTORS: dict[str, str] = {
    "system:intake": "Réception : enregistre l'e-mail et le masque",
    "system:worker": "Worker d'analyse : appelle l'IA en arrière-plan",
    "system:rules": "Moteur de règles : calcule la priorité",
    "system:retention": "Purge : efface les textes originaux après la durée de conservation",
    "ai:<modèle>": "Assistant IA : propose catégorie, champs et résumé — ne décide jamais",
    "ai:<fournisseur>": "IA externe branchée par clé d'API : propose (champion ou fantôme)",
}


def has_permission(role: str, permission: str) -> bool:
    info = ROLES.get(role)
    return info is not None and permission in info.permissions
