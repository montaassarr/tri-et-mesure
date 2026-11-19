"""Business vocabulary: e-mail categories, sender types, damage types, priorities.

Codes are stable identifiers (used in the database, the gold set and the LLM schema);
labels are what handlers see in the UI.
"""

from typing import Literal

Category = Literal[
    "declaration_sinistre",
    "pieces_justificatives",
    "relance_delai",
    "reclamation",
    "demande_avance_relogement",
    "resiliation",
    "question_garantie",
    "verification_authenticite",
    "autre",
]

CATEGORY_LABELS: dict[str, str] = {
    "declaration_sinistre": "Nouvelle déclaration de sinistre",
    "pieces_justificatives": "Envoi de pièces justificatives",
    "relance_delai": "Relance / question sur un délai",
    "reclamation": "Réclamation",
    "demande_avance_relogement": "Demande d'avance ou de relogement",
    "resiliation": "Résiliation",
    "question_garantie": "Question sur la garantie",
    "verification_authenticite": "« Ce message vient-il vraiment de mon assureur ? »",
    "autre": "Autre",
}

CATEGORIES: tuple[str, ...] = tuple(CATEGORY_LABELS)

SenderType = Literal["assure", "agent", "garage", "expert", "autre"]

SENDER_LABELS: dict[str, str] = {
    "assure": "Assuré",
    "agent": "Agent général",
    "garage": "Garage / réparateur",
    "expert": "Expert",
    "autre": "Autre",
}

DamageType = Literal[
    "degat_des_eaux",
    "incendie",
    "grele",
    "tempete",
    "vol",
    "bris_de_glace",
    "accident_auto",
    "catastrophe_naturelle",
    "autre",
]

DAMAGE_LABELS: dict[str, str] = {
    "degat_des_eaux": "Dégât des eaux",
    "incendie": "Incendie",
    "grele": "Grêle",
    "tempete": "Tempête",
    "vol": "Vol / cambriolage",
    "bris_de_glace": "Bris de glace",
    "accident_auto": "Accident automobile",
    "catastrophe_naturelle": "Catastrophe naturelle",
    "autre": "Autre",
}

Priority = Literal["urgente", "haute", "normale", "basse"]

PRIORITY_ORDER: dict[str, int] = {"urgente": 0, "haute": 1, "normale": 2, "basse": 3}

# Below this confidence, a case is routed to manual handling whatever the suggestion.
MANUAL_REVIEW_CONFIDENCE = 0.6
