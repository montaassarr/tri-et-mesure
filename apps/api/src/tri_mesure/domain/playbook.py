"""Team playbook: what a handler should do next, why, and within which deadline.

Deterministic business rules written by the team (not by the AI). They turn the extracted
facts into a short checklist, the regulatory frame that applies, and a reply template.
Regulatory references are reminders for a demo; internal procedures prevail.
"""

from dataclasses import dataclass, field

from tri_mesure.domain.schemas import ExtractedFields


@dataclass(frozen=True)
class Step:
    label: str
    why: str
    deadline: str | None = None
    urgent: bool = False


@dataclass(frozen=True)
class Frame:
    name: str
    summary: str
    deadlines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Playbook:
    steps: list[Step]
    frames: list[Frame]
    reply_subject: str
    reply_body: str


IRSI = Frame(
    "Convention IRSI (dégâts des eaux)",
    "Jusqu'à 1 600 € HT : l'assureur de l'occupant indemnise, sans expertise ni recours. "
    "De 1 600 à 5 000 € HT : l'assureur gestionnaire missionne une expertise. "
    "Au-delà de 5 000 € HT en copropriété : convention CIDE-COP.",
)
CATNAT = Frame(
    "Catastrophe naturelle (art. L125-2 Code des assurances)",
    "Applicable seulement après publication de l'arrêté interministériel pour la commune.",
    [
        "Informer l'assuré sous 1 mois",
        "Offre sous 1 mois après l'estimation",
        "Paiement sous 21 jours après accord",
    ],
)
BADINTER = Frame(
    "Loi Badinter (accident de la circulation)",
    "Offre d'indemnisation dans des délais légaux, sous peine d'intérêts au double du taux légal.",
    ["Dommages matériels : offre sous 3 mois", "Dommages corporels : offre sous 8 mois"],
)
COMPLAINT = Frame(
    "Traitement des réclamations (recommandation ACPR 2024-R-02)",
    "Accuser réception rapidement, répondre sur le fond, indiquer la voie de recours (médiateur).",
    ["Accusé de réception sous 10 jours ouvrables", "Réponse sous 2 mois au plus"],
)

REPLY_OPENING = "Madame, Monsieur,\n\n"
REPLY_CLOSING = (
    "\n\nNous restons à votre disposition.\n\nCordialement,\nVotre gestionnaire sinistres"
)


def _ref(fields: ExtractedFields) -> str:
    return f" (contrat {fields.numero_contrat})" if fields.numero_contrat else ""


def build(category: str, fields: ExtractedFields) -> Playbook:
    """Checklist + frames + reply template for one case. Pure function, unit-tested."""
    steps: list[Step] = []
    frames: list[Frame] = []
    ref = _ref(fields)

    # Human urgency first: these come before any paperwork.
    if fields.besoin_relogement:
        steps.append(
            Step(
                "Appeler l'assuré pour organiser un relogement",
                "Le logement est inhabitable : c'est la priorité humaine du dossier.",
                "sous 4 h",
                urgent=True,
            )
        )
    if fields.fuite_active:
        steps.append(
            Step(
                "Conseiller de couper l'eau et proposer un plombier d'urgence",
                "Une fuite active aggrave les dommages à chaque heure.",
                "immédiat",
                urgent=True,
            )
        )
    if fields.personne_vulnerable:
        steps.append(
            Step(
                "Signaler la vulnérabilité dans le dossier et adapter le suivi",
                "Une personne âgée, malade ou un nourrisson justifie un accompagnement renforcé.",
                urgent=True,
            )
        )

    if category == "declaration_sinistre":
        steps.append(
            Step(
                "Ouvrir le sinistre et vérifier les garanties à la date du sinistre",
                "Aucune indemnisation sans contrat actif et garantie couvrant ce dommage.",
            )
        )
        if fields.type_dommage == "degat_des_eaux":
            frames.append(IRSI)
            steps.append(
                Step(
                    "Estimer le montant pour choisir la tranche IRSI",
                    "Sous 1 600 € HT, pas d'expertise : traitement plus rapide.",
                )
            )
        elif fields.type_dommage == "catastrophe_naturelle":
            frames.append(CATNAT)
            steps.append(
                Step(
                    "Vérifier la publication de l'arrêté CatNat pour la commune",
                    "La garantie catastrophe naturelle ne joue qu'après l'arrêté.",
                )
            )
        elif fields.type_dommage in ("accident_auto", "bris_de_glace"):
            frames.append(BADINTER)
            steps.append(
                Step(
                    "Demander le constat amiable s'il manque",
                    "Il fixe les responsabilités entre assureurs.",
                )
            )
        elif fields.type_dommage == "vol":
            steps.append(
                Step(
                    "Demander le dépôt de plainte",
                    "Pièce obligatoire pour toute indemnisation d'un vol.",
                )
            )
        else:
            steps.append(
                Step(
                    "Demander photos et devis",
                    "Ils permettent d'évaluer le dommage sans attendre l'expert.",
                )
            )
        reply = (
            f"Nous avons bien reçu votre déclaration de sinistre{ref}. Un gestionnaire suit "
            "votre dossier. Pour accélérer son traitement, merci de nous adresser des photos "
            "des dommages et, si vous les avez, les devis ou factures."
        )
        subject = "Votre déclaration de sinistre"
    elif category == "pieces_justificatives":
        steps.append(
            Step(
                "Rattacher les pièces au dossier et vérifier qu'elles sont complètes",
                "Une pièce manquante est la première cause de relance client.",
            )
        )
        reply = (
            f"Nous avons bien reçu vos documents{ref}. Ils ont été ajoutés à votre dossier ; "
            "nous revenons vers vous si une pièce complémentaire est nécessaire."
        )
        subject = "Réception de vos documents"
    elif category == "relance_delai":
        steps.append(
            Step(
                "Retrouver le dossier et donner une date précise de prochaine étape",
                "Une relance non traitée devient souvent une réclamation.",
            )
        )
        reply = (
            f"Nous avons bien reçu votre message{ref} et nous excusons du délai. Votre dossier "
            "est en cours ; nous revenons vers vous avec une date précise sous 48 heures."
        )
        subject = "Suivi de votre dossier"
    elif category == "reclamation":
        frames.append(COMPLAINT)
        steps.append(
            Step(
                "Enregistrer la réclamation et accuser réception",
                "Obligation de traçabilité ; le délai réglementaire court dès réception.",
                "sous 10 jours ouvrables",
                urgent=True,
            )
        )
        steps.append(
            Step(
                "Informer le responsable d'équipe",
                "Une réclamation peut mener au médiateur : elle doit être suivie.",
            )
        )
        reply = (
            f"Nous avons bien reçu votre réclamation{ref}. Elle est enregistrée et sera "
            "examinée avec attention ; une réponse vous sera apportée au plus tard sous deux "
            "mois. En cas de désaccord persistant, vous pourrez saisir le Médiateur de "
            "l'Assurance."
        )
        subject = "Accusé de réception de votre réclamation"
    elif category == "demande_avance_relogement":
        steps.append(
            Step(
                "Valider l'hébergement d'urgence prévu au contrat",
                "La garantie relogement est souvent incluse en multirisque habitation.",
            )
        )
        steps.append(
            Step(
                "Étudier une avance sur indemnité",
                "Une avance évite de laisser l'assuré sans solution pendant l'expertise.",
            )
        )
        reply = (
            f"Nous avons bien reçu votre demande{ref}. Un gestionnaire vous appelle "
            "aujourd'hui pour organiser votre hébergement et étudier une avance."
        )
        subject = "Votre demande de relogement"
    elif category == "resiliation":
        steps.append(
            Step(
                "Transmettre au service contrats",
                "La résiliation n'est pas gérée par le service sinistres.",
            )
        )
        reply = (
            f"Nous avons bien reçu votre demande de résiliation{ref}. Elle a été transmise au "
            "service contrats, qui vous confirmera la date de prise d'effet."
        )
        subject = "Votre demande de résiliation"
    elif category == "question_garantie":
        steps.append(
            Step(
                "Vérifier les garanties et la franchise du contrat",
                "Répondre précisément évite une déclaration inutile ou un litige.",
            )
        )
        reply = (
            f"Merci pour votre question{ref}. Après vérification de votre contrat, nous vous "
            "précisons les garanties et la franchise applicables dans un prochain message."
        )
        subject = "Votre question sur vos garanties"
    elif category == "verification_authenticite":
        steps.append(
            Step(
                "Confirmer qu'il s'agit d'une tentative de fraude et rassurer l'assuré",
                "L'assureur ne demande jamais de paiement ni de coordonnées bancaires par SMS.",
                "aujourd'hui",
                urgent=True,
            )
        )
        steps.append(
            Step(
                "Signaler le message à l'équipe sécurité",
                "Plusieurs signalements identiques révèlent une campagne d'hameçonnage.",
            )
        )
        reply = (
            "Merci de votre vigilance. Ce message ne vient pas de nous : nous ne demandons "
            "jamais de paiement ni de coordonnées bancaires par SMS ou par lien. Ne cliquez "
            "pas et supprimez-le. Votre dossier n'est pas concerné."
        )
        subject = "Message frauduleux : ne cliquez pas"
    else:
        steps.append(
            Step(
                "Répondre ou transmettre au bon service", "Ce message ne relève pas d'un sinistre."
            )
        )
        reply = "Nous avons bien reçu votre message et y donnons suite rapidement."
        subject = "Votre message"

    return Playbook(steps, frames, subject, REPLY_OPENING + reply + REPLY_CLOSING)
