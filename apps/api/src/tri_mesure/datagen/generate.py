"""Synthetic French claim e-mails with known ground truth.

Each e-mail is generated from a structured *seed* first (category, sender, fields) and then
rendered as text, so the seed **is** the label: nothing is hand-guessed after the fact, and
no real person's data is involved (identities come from Faker fr_FR; contract numbers use a
fictitious CTnnnnnnnn format). Output is deterministic for a given --seed.

Usage:  python -m tri_mesure.datagen.generate --out data/gold [--seed 42]
Writes: dev.jsonl (40), test.jsonl (80), demo.jsonl (80) and ci.jsonl (first 30 of test).
"""

import argparse
import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

MONTHS_FR = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
START = date(2026, 9, 1)
END = date(2026, 11, 17)
CLOSINGS = [
    "Cordialement,",
    "Bien cordialement,",
    "Bien à vous,",
    "Merci d'avance,",
    "Salutations distinguées,",
]


@dataclass
class Expected:
    category: str
    sender_type: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sample:
    id: str
    received_at: str
    sender_email: str
    subject: str
    body: str
    expected: Expected
    tags: list[str] = field(default_factory=list)


class Ctx:
    """Random helpers bound to one generator instance (deterministic)."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.fake = Faker("fr_FR")
        self.fake.seed_instance(seed)
        self.storm: str | None = None  # set by generate_storm(): "grele" | "tempete" | "inondation"

    def damage(self, options: list[str], vehicle: bool) -> str:
        """Damage type: random in normal times, imposed by the event in storm mode."""
        if self.storm is None:
            return str(self.pick(options))
        if self.storm == "grele":
            return "grele"
        if self.storm == "tempete":
            return "bris_de_glace" if vehicle else "tempete"
        return "catastrophe_naturelle"  # inondation

    def pick(self, items: list[Any]) -> Any:
        return self.rng.choice(items)

    def pick_str(self, items: list[str]) -> str:
        return self.rng.choice(items)

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def contract(self) -> str:
        return f"CT{self.rng.randint(10_000_000, 99_999_999)}"

    def plate(self) -> str:
        letters = "ABCDEFGHJKLMNPQRSTVWXYZ"
        a = "".join(self.rng.choice(letters) for _ in range(2))
        b = "".join(self.rng.choice(letters) for _ in range(2))
        return f"{a}-{self.rng.randint(100, 999)}-{b}"

    def phone(self) -> str:
        first = self.pick(["06", "07", "01", "04"])
        rest = " ".join(f"{self.rng.randint(0, 99):02d}" for _ in range(4))
        return f"{first} {rest}"

    def iban(self) -> str:
        digits = "".join(str(self.rng.randint(0, 9)) for _ in range(23))
        groups = [digits[i : i + 4] for i in range(0, 20, 4)] + [digits[20:]]
        return f"FR{self.rng.randint(10, 99)} " + " ".join(groups)

    def person(self) -> tuple[str, str]:
        civ = self.pick(["M.", "Mme"])
        first = self.fake.first_name_male() if civ == "M." else self.fake.first_name_female()
        return civ, f"{first} {self.fake.last_name()}"

    def address(self) -> str:
        street = self.pick(["rue", "avenue", "boulevard", "chemin", "allée", "impasse"])
        name = self.fake.last_name()
        return (
            f"{self.rng.randint(1, 180)} {street} {self.pick(['des', 'du', 'de la'])} "
            f"{name}, {self.fake.postcode()} {self.fake.city()}"
        )


def fmt_date(ctx: Ctx, d: date, received: date) -> str:
    if d == received - timedelta(days=1) and ctx.chance(0.5):
        return "hier"
    if ctx.chance(0.5):
        return f"le {d.day} {MONTHS_FR[d.month - 1]}"
    return f"le {d.day:02d}/{d.month:02d}/{d.year}"


def signature(ctx: Ctx, name: str, with_phone: bool = True) -> tuple[str, str]:
    phone = ctx.phone()
    lines = [ctx.pick(CLOSINGS), name]
    if with_phone:
        lines.append(f"Tél : {phone}")
    return "\n".join(lines), phone


# --- category renderers ---------------------------------------------------------------
# Each returns (subject, body, expected_fields, sender_type, tags).

Rendered = tuple[str, str, dict[str, Any], str, list[str]]

HOME_DAMAGES = ["degat_des_eaux", "incendie", "tempete", "vol", "grele", "catastrophe_naturelle"]
AUTO_DAMAGES = ["accident_auto", "bris_de_glace", "grele", "vol"]


def _home_damage_text(ctx: Ctx, damage: str) -> str:
    texts: dict[str, str] = {
        "degat_des_eaux": ctx.pick(
            [
                "une canalisation a cédé sous l'évier de la cuisine",
                "le chauffe-eau a fui et l'eau s'est répandue dans le séjour",
                "une infiltration par la toiture a abîmé le plafond de la chambre",
            ]
        ),
        "incendie": ctx.pick(
            [
                "un incendie s'est déclaré dans la cuisine",
                "un départ de feu dans le garage a abîmé une partie de la maison",
            ]
        ),
        "tempete": ctx.pick(
            [
                "la tempête a arraché une partie de la toiture",
                "un arbre est tombé sur la véranda pendant la tempête",
            ]
        ),
        "vol": ctx.pick(
            [
                "notre maison a été cambriolée pendant notre absence",
                "nous avons été victimes d'un cambriolage avec effraction de la porte d'entrée",
            ]
        ),
        "grele": "un violent orage de grêle a cassé plusieurs tuiles et la verrière",
        "catastrophe_naturelle": ctx.pick(
            [
                "des fissures importantes sont apparues sur les murs après la sécheresse de l'été",
                "notre sous-sol a été inondé lors de la crue, la commune a fait une demande de "
                "reconnaissance en catastrophe naturelle",
            ]
        ),
    }
    return texts[damage]


def _auto_damage_text(ctx: Ctx, damage: str) -> str:
    texts: dict[str, str] = {
        "accident_auto": ctx.pick(
            [
                "j'ai été percuté à l'arrière à un feu rouge",
                "un véhicule m'a accroché en sortant d'un parking",
            ]
        ),
        "bris_de_glace": "un gravillon a fissuré le pare-brise sur l'autoroute",
        "grele": "la grêle a cabossé le capot et le toit de ma voiture",
        "vol": "ma voiture a été volée devant mon domicile",
    }
    return texts[damage]


def render_declaration(ctx: Ctx, received: date) -> Rendered:
    _, name = ctx.person()
    contract = ctx.contract()
    d = received - timedelta(days=ctx.rng.randint(0, 1 if ctx.storm else 6))
    fields: dict[str, Any] = {"numero_contrat": contract, "date_sinistre": d.isoformat()}
    tags: list[str] = []

    if ctx.chance(0.35) and ctx.storm != "inondation":
        damage = ctx.damage(AUTO_DAMAGES, vehicle=True)
        plate = ctx.plate()
        fields.update(type_dommage=damage, immatriculation=plate)
        opening = ctx.pick(
            [
                "Bonjour, je souhaite déclarer un sinistre automobile.",
                "Madame, Monsieur, je vous contacte pour déclarer un sinistre sur mon véhicule.",
                "Bonjour,",
            ]
        )
        body = (
            f"{opening}\n\n{fmt_date(ctx, d, received).capitalize()}, "
            f"{_auto_damage_text(ctx, damage)}. Il s'agit de mon véhicule immatriculé "
            f"{plate}, assuré sous le contrat {contract}."
        )
        if damage == "accident_auto" and ctx.chance(0.6):
            body += " Nous avons rempli un constat amiable, je vous l'enverrai dès que possible."
        subject = ctx.pick(
            [
                "Déclaration de sinistre auto",
                "Sinistre véhicule",
                f"Accident - contrat {contract}",
                "Pare-brise / sinistre",
            ]
        )
    else:
        damage = ctx.damage(HOME_DAMAGES, vehicle=False)
        address = ctx.address()
        fields.update(type_dommage=damage, adresse_sinistre=address)
        tone = ctx.pick(["formal", "stressed", "terse"])
        if tone == "formal":
            body = (
                f"Madame, Monsieur,\n\nJe vous écris pour déclarer un sinistre survenu "
                f"{fmt_date(ctx, d, received)} à mon domicile, {address} : "
                f"{_home_damage_text(ctx, damage)}. Mon numéro de contrat est {contract}."
            )
        elif tone == "stressed":
            body = (
                f"Bonjour,\n\nC'est une catastrophe, {_home_damage_text(ctx, damage)} "
                f"{fmt_date(ctx, d, received)}. L'adresse : {address}. "
                f"Contrat {contract}. Je ne sais pas quoi faire, merci de me rappeler vite."
            )
        else:
            body = (
                f"Bonjour, sinistre {fmt_date(ctx, d, received)} au {address} : "
                f"{_home_damage_text(ctx, damage)}. Contrat {contract}."
            )
        if damage == "degat_des_eaux":
            if ctx.chance(0.5):
                fields["fuite_active"] = True
                body += " L'eau coule encore malgré la fermeture du compteur."
                tags.append("urgent")
            else:
                fields["fuite_active"] = False
                body += " Le plombier a réparé la fuite ce matin."
        if damage in {
            "degat_des_eaux",
            "incendie",
            "tempete",
            "catastrophe_naturelle",
        } and ctx.chance(0.3):
            fields["besoin_relogement"] = True
            body += " La maison n'est plus habitable pour l'instant."
            tags.append("urgent")
        if ctx.chance(0.15):
            fields["personne_vulnerable"] = True
            body += ctx.pick(
                [
                    f" Ma mère de {ctx.rng.randint(82, 94)} ans vit avec nous.",
                    " Nous avons un nourrisson à la maison.",
                    " Mon mari est en fauteuil roulant.",
                ]
            )
            tags.append("urgent")
        subject = ctx.pick(
            [
                "Déclaration de sinistre",
                "Sinistre habitation",
                "Urgent - dégâts à la maison",
                f"Déclaration contrat {contract}",
            ]
        )

    if ctx.chance(0.3):
        body += " Je joins quelques photos."
        tags.append("multi-intent")
    sig, _ = signature(ctx, name)
    return subject, f"{body}\n\n{sig}", fields, "assure", tags


def render_pieces(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    d = received - timedelta(days=ctx.rng.randint(5, 30))
    kind = ctx.pick(["assure", "assure", "garage", "expert"])
    fields: dict[str, Any] = {"numero_contrat": contract}
    if kind == "garage":
        plate = ctx.plate()
        garage = f"Garage {ctx.fake.last_name()}"
        fields.update(immatriculation=plate, type_dommage="accident_auto")
        body = (
            f"Bonjour,\n\nVeuillez trouver ci-joint le devis de réparation du véhicule "
            f"immatriculé {plate} (contrat {contract}), suite à l'accident déclaré par votre "
            f"assuré. Le montant s'élève à {ctx.rng.randint(800, 4500)} € TTC.\n\n"
            f"Cordialement,\n{garage} - carrosserie\nTél : {ctx.phone()}"
        )
        return "Devis réparation véhicule", body, fields, "garage", []
    if kind == "expert":
        _, name = ctx.person()
        body = (
            f"Bonjour,\n\nVous trouverez en pièce jointe le rapport d'expertise concernant le "
            f"dossier du contrat {contract}, visite effectuée {fmt_date(ctx, d, received)}.\n\n"
            f"Bien cordialement,\n{name}\nCabinet d'expertise {ctx.fake.last_name()}"
        )
        return f"Rapport d'expertise {contract}", body, fields, "expert", []
    _, name = ctx.person()
    fields["date_sinistre"] = d.isoformat()
    body = (
        f"Bonjour,\n\nSuite à ma déclaration du sinistre survenu {fmt_date(ctx, d, received)}, "
        f"je vous transmets {ctx.pick(['les photos des dégâts', 'la facture du plombier', 'le constat amiable signé', 'le dépôt de plainte'])} "
        f"pour le contrat {contract}."
    )
    if ctx.chance(0.3):
        iban = ctx.iban()
        body += f" Pour le remboursement, mon IBAN est {iban}."
    sig, _ = signature(ctx, name)
    return (
        ctx.pick(["Pièces justificatives", "Documents sinistre", "Envoi photos"]),
        f"{body}\n\n{sig}",
        fields,
        "assure",
        [],
    )


def render_relance(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    d = received - timedelta(days=ctx.rng.randint(15, 60))
    fields: dict[str, Any] = {"numero_contrat": contract, "date_sinistre": d.isoformat()}
    tags: list[str] = []
    if ctx.chance(0.25):
        civ, client = ctx.person()
        _, agent = ctx.person()
        body = (
            f"Bonjour,\n\nMon client {civ} {client} (contrat {contract}) attend toujours "
            f"le passage de l'expert pour son sinistre du {d.day} {MONTHS_FR[d.month - 1]}. "
            f"Pouvez-vous me dire où en est le dossier ?\n\nCordialement,\n{agent}\n"
            f"Agent général - Agence {ctx.fake.city()}"
        )
        return "Relance dossier client", body, fields, "agent", tags
    _, name = ctx.person()
    weeks = ctx.pick(["deux", "trois", "quatre", "cinq"])
    body = (
        f"Bonjour,\n\nJe me permets de vous relancer concernant mon sinistre survenu "
        f"{fmt_date(ctx, d, received)} (contrat {contract}). Je suis toujours sans nouvelles "
        f"depuis {weeks} semaines."
    )
    if ctx.chance(0.4):
        e = received + timedelta(days=ctx.rng.randint(1, 20))
        fields["echeance"] = e.isoformat()
        body += f" L'artisan doit commencer les travaux avant le {e.day} {MONTHS_FR[e.month - 1]}."
    sig, _ = signature(ctx, name)
    return (
        ctx.pick(["Relance", "Toujours sans nouvelles", f"Relance dossier {contract}"]),
        f"{body}\n\n{sig}",
        fields,
        "assure",
        tags,
    )


def render_reclamation(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    _, name = ctx.person()
    fields: dict[str, Any] = {"numero_contrat": contract}
    body = ctx.pick(
        [
            f"Bonjour,\n\nJe conteste fermement le rapport de l'expert sur mon dossier (contrat "
            f"{contract}). Le montant proposé ne couvre même pas la moitié des réparations. "
            f"C'est inadmissible.",
            f"Madame, Monsieur,\n\nCela fait deux mois que j'attends et on me refuse maintenant la "
            f"prise en charge sans explication. Je suis très mécontent du traitement de mon dossier "
            f"{contract}.",
            f"Bonjour,\n\nVotre refus d'indemnisation est inacceptable, mon contrat {contract} "
            f"prévoit bien cette garantie.",
        ]
    )
    if ctx.chance(0.5):
        body += " Sans réponse sous quinze jours, je saisirai le médiateur de l'assurance."
    sig, _ = signature(ctx, name)
    return (
        ctx.pick(["Réclamation", "Contestation expertise", "Mécontentement"]),
        f"{body}\n\n{sig}",
        fields,
        "assure",
        [],
    )


def render_avance(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    _, name = ctx.person()
    d = received - timedelta(days=ctx.rng.randint(0, 1) if ctx.storm else ctx.rng.randint(1, 15))
    damage = "tempete" if ctx.storm else ctx.pick(["incendie", "degat_des_eaux", "tempete"])
    fields: dict[str, Any] = {
        "numero_contrat": contract,
        "date_sinistre": d.isoformat(),
        "type_dommage": damage,
        "besoin_relogement": True,
    }
    cause = {
        "incendie": "l'incendie",
        "degat_des_eaux": "le dégât des eaux",
        "tempete": "la tempête",
    }[damage]
    body = (
        f"Bonjour,\n\nDepuis {cause} survenu {fmt_date(ctx, d, received)}, notre logement "
        f"est inhabitable et nous sommes hébergés chez des amis. Pouvez-vous nous accorder une "
        f"avance sur l'indemnisation et la prise en charge d'un hébergement ? Contrat {contract}."
    )
    tags = ["urgent"]
    if ctx.chance(0.3):
        fields["personne_vulnerable"] = True
        body += " Nous avons un bébé de quatre mois."
    sig, _ = signature(ctx, name)
    return (
        ctx.pick(["Demande d'avance", "Relogement urgent", "Besoin d'aide - hébergement"]),
        f"{body}\n\n{sig}",
        fields,
        "assure",
        tags,
    )


def render_resiliation(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    _, name = ctx.person()
    move = received + timedelta(days=ctx.rng.randint(10, 40))
    body = ctx.pick(
        [
            f"Bonjour,\n\nJe souhaite résilier mon contrat habitation {contract} car je déménage "
            f"à l'étranger le {move.day} {MONTHS_FR[move.month - 1]}.",
            f"Madame, Monsieur,\n\nPar la présente, je vous informe de ma volonté de mettre fin à mon "
            f"contrat {contract} à sa prochaine échéance.",
            f"Bonjour, comment résilier mon contrat auto {contract} ? J'ai vendu le véhicule.",
        ]
    )
    sig, _ = signature(ctx, name, with_phone=ctx.chance(0.5))
    return (
        ctx.pick(["Résiliation", "Résiliation contrat", "Fin de contrat"]),
        f"{body}\n\n{sig}",
        {"numero_contrat": contract},
        "assure",
        ["trap-date"],
    )


def render_question(ctx: Ctx, received: date) -> Rendered:
    contract = ctx.contract()
    _, name = ctx.person()
    damage, text = ctx.pick(
        [
            ("grele", "les dégâts de grêle sur une véranda"),
            ("degat_des_eaux", "une fuite venant de chez le voisin du dessus"),
            ("vol", "le vol d'un vélo électrique dans le local commun"),
            ("bris_de_glace", "le remplacement d'un pare-brise"),
        ]
    )
    body = (
        f"Bonjour,\n\nEst-ce que mon contrat {contract} couvre {text} ? "
        f"{ctx.pick(['Quelle serait la franchise ?', 'Y a-t-il un plafond ?', 'Merci de me préciser les conditions.'])}"
    )
    sig, _ = signature(ctx, name, with_phone=False)
    return (
        ctx.pick(["Question sur ma garantie", "Couverture ?", "Renseignement contrat"]),
        f"{body}\n\n{sig}",
        {"numero_contrat": contract, "type_dommage": damage},
        "assure",
        [],
    )


def render_authenticite(ctx: Ctx, received: date) -> Rendered:
    _, name = ctx.person()
    fields: dict[str, Any] = {}
    body = ctx.pick(
        [
            "Bonjour,\n\nJ'ai reçu un SMS me demandant de payer 1,99 € pour débloquer le "
            "remboursement de mon sinistre, avec un lien. Est-ce que ce message vient vraiment de "
            "vous ?",
            "Bonjour,\n\nOn m'a appelé en se présentant comme votre service sinistres et on m'a "
            "demandé mon IBAN. Est-ce bien vous ? Cela ressemble à une arnaque.",
            "Bonjour, un e-mail me dit que mes données ont fuité et me demande de me reconnecter via "
            "un lien. Est-ce légitime ?",
        ]
    )
    if ctx.chance(0.5):
        contract = ctx.contract()
        fields["numero_contrat"] = contract
        body += f" Mon contrat est le {contract}."
    sig, _ = signature(ctx, name, with_phone=ctx.chance(0.5))
    return (
        ctx.pick(["Message suspect ?", "Est-ce une arnaque ?", "SMS bizarre"]),
        f"{body}\n\n{sig}",
        fields,
        "assure",
        ["security"],
    )


def render_autre(ctx: Ctx, received: date) -> Rendered:
    _, name = ctx.person()
    body = ctx.pick(
        [
            "Bonjour,\n\nPouvez-vous m'envoyer une attestation d'assurance habitation pour mon "
            "propriétaire ?",
            "Bonjour, je change d'adresse e-mail, merci de mettre à jour mon dossier.",
            "Bonjour,\n\nMerci beaucoup pour votre aide la semaine dernière, tout est réglé.",
            "Bonjour, quels sont les horaires de l'agence pendant les fêtes ?",
        ]
    )
    sig, _ = signature(ctx, name, with_phone=ctx.chance(0.3))
    return ctx.pick(["Demande", "Information", "Question"]), f"{body}\n\n{sig}", {}, "assure", []


RENDERERS: list[tuple[str, float, Callable[[Ctx, date], Rendered]]] = [
    ("declaration_sinistre", 0.24, render_declaration),
    ("pieces_justificatives", 0.13, render_pieces),
    ("relance_delai", 0.13, render_relance),
    ("reclamation", 0.10, render_reclamation),
    ("demande_avance_relogement", 0.08, render_avance),
    ("resiliation", 0.08, render_resiliation),
    ("question_garantie", 0.09, render_question),
    ("verification_authenticite", 0.07, render_authenticite),
    ("autre", 0.08, render_autre),
]


def generate(n: int, seed: int) -> list[Sample]:
    ctx = Ctx(seed)
    names = [r[0] for r in RENDERERS]
    weights = [r[1] for r in RENDERERS]
    renderers = {r[0]: r[2] for r in RENDERERS}
    samples: list[Sample] = []
    for i in range(n):
        # Guarantee every category appears: the first len(RENDERERS) samples cycle through them.
        category = names[i] if i < len(names) else ctx.rng.choices(names, weights)[0]
        received = START + timedelta(days=ctx.rng.randint(0, (END - START).days))
        subject, body, fields, sender, tags = renderers[category](ctx, received)
        received_at = datetime(
            received.year,
            received.month,
            received.day,
            ctx.rng.randint(7, 21),
            ctx.rng.randint(0, 59),
        ).isoformat()
        samples.append(
            Sample(
                id=f"m{i + 1:04d}",
                received_at=received_at,
                sender_email=ctx.fake.free_email(),
                subject=subject,
                body=body,
                expected=Expected(category=category, sender_type=sender, fields=fields),
                tags=tags,
            )
        )
    ctx.rng.shuffle(samples)
    return samples


def write_jsonl(path: Path, samples: list[Sample]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for s in samples:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/gold"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    samples = generate(200, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    dev, test, demo = samples[:40], samples[40:120], samples[120:]
    write_jsonl(args.out / "dev.jsonl", dev)
    write_jsonl(args.out / "test.jsonl", test)
    write_jsonl(args.out / "demo.jsonl", demo)
    write_jsonl(args.out / "ci.jsonl", test[:30])
    print(f"Wrote {len(dev)} dev, {len(test)} test, {len(demo)} demo, 30 ci to {args.out}")


if __name__ == "__main__":
    main()


STORM_MIX: list[tuple[str, float]] = [
    ("declaration_sinistre", 0.55),
    ("demande_avance_relogement", 0.15),
    ("relance_delai", 0.08),
    ("question_garantie", 0.06),
    ("verification_authenticite", 0.10),  # fake "remboursement" SMS follow every storm
    ("pieces_justificatives", 0.06),
]


def generate_storm(n: int, seed: int, kind: str, received: date) -> list[Sample]:
    """A burst of e-mails after a climate event: same day, damage imposed by the event."""
    if kind not in ("grele", "tempete", "inondation"):
        raise ValueError(f"Unknown event kind: {kind}")
    ctx = Ctx(seed)
    ctx.storm = kind
    renderers = {r[0]: r[2] for r in RENDERERS}
    names = [c for c, _ in STORM_MIX]
    weights = [w for _, w in STORM_MIX]
    samples: list[Sample] = []
    for i in range(n):
        category = ctx.rng.choices(names, weights)[0]
        subject, body, fields, sender, tags = renderers[category](ctx, received)
        received_at = datetime(
            received.year,
            received.month,
            received.day,
            ctx.rng.randint(6, 20),
            ctx.rng.randint(0, 59),
        ).isoformat()
        samples.append(
            Sample(
                id=f"storm{seed}-{i + 1:04d}",
                received_at=received_at,
                sender_email=ctx.fake.free_email(),
                subject=subject,
                body=body,
                expected=Expected(category=category, sender_type=sender, fields=fields),
                tags=[*tags, f"event:{kind}"],
            )
        )
    return samples
