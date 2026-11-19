"""Extraction schema shared by every LLM provider, the gold set and the API.

`Extraction` is the exact shape a model must return. It is passed to Claude's structured
outputs (and to OpenAI-compatible JSON-schema mode), so keep it free of validation
constraints that JSON-schema-constrained decoding may not support; `normalise()` clamps
and cleans values after parsing instead.
"""

from typing import Literal

from pydantic import BaseModel, Field

from tri_mesure.domain.taxonomy import Category, DamageType, SenderType

FieldName = Literal[
    "numero_contrat",
    "date_sinistre",
    "adresse_sinistre",
    "type_dommage",
    "immatriculation",
    "besoin_relogement",
    "fuite_active",
    "personne_vulnerable",
    "echeance",
]

FIELD_NAMES: tuple[str, ...] = (
    "numero_contrat",
    "date_sinistre",
    "adresse_sinistre",
    "type_dommage",
    "immatriculation",
    "besoin_relogement",
    "fuite_active",
    "personne_vulnerable",
    "echeance",
)

FIELD_LABELS: dict[str, str] = {
    "numero_contrat": "N° de contrat",
    "date_sinistre": "Date du sinistre",
    "adresse_sinistre": "Adresse du sinistre",
    "type_dommage": "Type de dommage",
    "immatriculation": "Immatriculation",
    "besoin_relogement": "Besoin de relogement",
    "fuite_active": "Fuite toujours active",
    "personne_vulnerable": "Personne vulnérable",
    "echeance": "Échéance mentionnée",
}


class ExtractedFields(BaseModel):
    numero_contrat: str | None = Field(
        default=None, description="Numéro de contrat tel qu'écrit (ou son jeton masqué)."
    )
    date_sinistre: str | None = Field(
        default=None, description="Date du sinistre au format AAAA-MM-JJ, si indiquée."
    )
    adresse_sinistre: str | None = Field(
        default=None, description="Adresse du lieu du sinistre, si indiquée."
    )
    type_dommage: DamageType | None = None
    immatriculation: str | None = Field(
        default=None, description="Plaque d'immatriculation (ou son jeton masqué)."
    )
    besoin_relogement: bool | None = Field(
        default=None, description="Vrai si l'expéditeur dit ne plus pouvoir loger chez lui."
    )
    fuite_active: bool | None = Field(
        default=None, description="Vrai si une fuite d'eau est toujours en cours."
    )
    personne_vulnerable: bool | None = Field(
        default=None,
        description="Vrai si une personne âgée, malade, handicapée ou un nourrisson est concerné.",
    )
    echeance: str | None = Field(
        default=None,
        description="Date limite ou rendez-vous mentionné, au format AAAA-MM-JJ.",
    )


class Evidence(BaseModel):
    field: FieldName
    quote: str = Field(description="Extrait exact du texte de l'e-mail qui justifie la valeur.")


class Extraction(BaseModel):
    """What the model must return for one e-mail."""

    category: Category
    sender_type: SenderType
    confidence: float = Field(description="Confiance dans la catégorie, entre 0 et 1.")
    fields: ExtractedFields
    evidence: list[Evidence] = Field(
        default_factory=list, description="Une citation exacte par champ renseigné."
    )
    summary: str = Field(description="Résumé neutre en deux phrases maximum, en français.")

    def normalise(self) -> "Extraction":
        """Clamp confidence and drop evidence for fields that were not filled."""
        filled = {k for k, v in self.fields.model_dump().items() if v is not None}
        return self.model_copy(
            update={
                "confidence": min(1.0, max(0.0, self.confidence)),
                "evidence": [e for e in self.evidence if e.field in filled],
                "summary": self.summary.strip(),
            }
        )


# How fields are grouped on screen: few groups, in the order a handler reads a claim.
FIELD_GROUPS: list[tuple[str, list[str]]] = [
    ("Contrat et véhicule", ["numero_contrat", "immatriculation"]),
    ("Sinistre", ["date_sinistre", "adresse_sinistre", "type_dommage"]),
    ("Signaux d'urgence", ["besoin_relogement", "fuite_active", "personne_vulnerable", "echeance"]),
]
assert sorted(f for _, group in FIELD_GROUPS for f in group) == sorted(FIELD_NAMES)
