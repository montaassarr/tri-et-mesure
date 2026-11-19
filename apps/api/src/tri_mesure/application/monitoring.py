"""Drift and health alerts for the AI in production.

A model rarely breaks loudly: it gets quietly worse (vendor update, new kind of e-mail,
prompt change). Handlers notice first: they start correcting more. This module turns
their corrections into an early-warning signal, next to the classic operational alerts.
"""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.application.ai_config import spent_today_eur
from tri_mesure.application.analysis import queue_depth
from tri_mesure.application.sources import get_champion
from tri_mesure.db.models import Email, Review, Suggestion
from tri_mesure.domain.schemas import FIELD_LABELS
from tri_mesure.observability import AI_ACCEPTANCE
from tri_mesure.settings import Settings

RECENT_WINDOW = 10  # last N decisions
BASELINE_WINDOW = 30  # the N decisions before those
MIN_DECISIONS = 5
DRIFT_DROP = 0.15  # 15-point drop in category acceptance
FIELD_CORRECTION_LIMIT = 0.40
FALLBACK_LIMIT = 0.20
QUEUE_LIMIT = 50

Severity = Literal["critique", "attention", "info"]
_ORDER = {"critique": 0, "attention": 1, "info": 2}


@dataclass(frozen=True)
class Alert:
    code: str
    severity: Severity
    title: str
    detail: str
    action: str


def _accept_rate(reviews: list[Review]) -> float | None:
    if not reviews:
        return None
    return sum(r.verdicts.get("category") == "accepted" for r in reviews) / len(reviews)


async def _champion_reviews(session: AsyncSession, champion: str) -> list[Review]:
    """AI-arm decisions on suggestions produced by the current champion, oldest first."""
    rows = await session.execute(
        select(Review)
        .join(Suggestion, Suggestion.id == Review.suggestion_id)
        .where(Review.arm == "ai", Suggestion.source == champion)
        .order_by(Review.created_at)
    )
    return list(rows.scalars())


async def compute_alerts(session: AsyncSession, settings: Settings) -> list[dict[str, Any]]:
    alerts: list[Alert] = []
    champion = await get_champion(session)
    reviews = await _champion_reviews(session, champion)

    recent = reviews[-RECENT_WINDOW:]
    baseline = reviews[-(RECENT_WINDOW + BASELINE_WINDOW) : -RECENT_WINDOW]
    r_rate, b_rate = _accept_rate(recent), _accept_rate(baseline)
    if r_rate is not None:
        AI_ACCEPTANCE.labels(champion).set(r_rate)
    if (
        r_rate is not None
        and b_rate is not None
        and len(recent) >= MIN_DECISIONS
        and len(baseline) >= MIN_DECISIONS
        and b_rate - r_rate >= DRIFT_DROP
    ):
        alerts.append(
            Alert(
                "drift.category",
                "critique",
                "Dérive de qualité détectée",
                f"Catégorie acceptée sans correction : {r_rate:.0%} sur les {len(recent)} derniers "
                f"dossiers, contre {b_rate:.0%} avant (source « {champion} »).",
                "Comparez avec une source en mode fantôme, ou revenez à la configuration "
                "précédente.",
            )
        )

    window = reviews[-BASELINE_WINDOW:]
    counts: dict[str, list[int]] = {}
    for r in window:
        for item, verdict in r.verdicts.items():
            if item == "category":
                continue
            c = counts.setdefault(item, [0, 0])
            c[1] += 1
            c[0] += verdict in ("edited", "rejected")
    for item, (corrected, n) in counts.items():
        if n >= MIN_DECISIONS * 2 and corrected / n >= FIELD_CORRECTION_LIMIT:
            alerts.append(
                Alert(
                    f"field.{item}",
                    "attention",
                    f"Champ souvent corrigé : {FIELD_LABELS.get(item, item)}",
                    f"{corrected / n:.0%} des valeurs proposées corrigées ou rejetées "
                    f"({n} décisions).",
                    "Piste d'amélioration du prompt : ajoutez un exemple ou une consigne "
                    "pour ce champ.",
                )
            )

    recent_suggestions = list(
        (
            await session.execute(
                select(Suggestion.used_fallback)
                .where(Suggestion.source == "interne")
                .order_by(Suggestion.id.desc())
                .limit(50)
            )
        ).scalars()
    )
    if len(recent_suggestions) >= 10:
        fb = sum(recent_suggestions) / len(recent_suggestions)
        if fb >= FALLBACK_LIMIT:
            alerts.append(
                Alert(
                    "ops.fallback",
                    "critique",
                    "Repli fréquent sur les règles",
                    f"{fb:.0%} des 50 dernières analyses n'ont pas pu utiliser le modèle.",
                    "Vérifiez la clé, le quota et le budget du fournisseur (écran Configuration).",
                )
            )

    failed = int(
        (
            await session.execute(
                select(func.count()).select_from(Email).where(Email.analysis_status == "failed")
            )
        ).scalar_one()
    )
    if failed:
        alerts.append(
            Alert(
                "ops.failed",
                "attention",
                f"{failed} analyse(s) en échec",
                "Ces dossiers sont traités sans proposition de l'IA.",
                "Corrigez la cause, puis « Réanalyser les dossiers ouverts ».",
            )
        )

    depth = await queue_depth(session)
    if depth > QUEUE_LIMIT:
        alerts.append(
            Alert(
                "ops.queue",
                "attention",
                f"File d'analyse chargée : {depth} e-mails",
                "Le worker ne suit pas le volume entrant (pic d'activité ou modèle lent).",
                "Augmentez WORKER_CONCURRENCY ou démarrez un worker supplémentaire.",
            )
        )

    spent = await spent_today_eur(session)
    if settings.daily_budget_eur > 0 and spent >= 0.8 * settings.daily_budget_eur:
        over = spent >= settings.daily_budget_eur
        alerts.append(
            Alert(
                "ops.budget",
                "critique" if over else "attention",
                "Budget du jour atteint" if over else "Budget du jour bientôt atteint",
                f"{spent:.4f} € dépensés sur {settings.daily_budget_eur:.2f} €.",
                "Au-delà, repli automatique sur les règles jusqu'à minuit (UTC).",
            )
        )

    alerts.sort(key=lambda a: _ORDER[a.severity])
    return [asdict(a) for a in alerts]
