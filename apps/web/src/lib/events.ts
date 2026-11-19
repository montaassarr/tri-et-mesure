import type { Tone } from "@/components/ui";

/** Event codes in plain French. */
export const EVENT_LABELS: Record<string, { label: string; tone: Tone }> = {
  "email.received": { label: "E-mail reçu", tone: "neutral" },
  "pii.masked": { label: "Données personnelles masquées", tone: "ok" },
  "ai.suggested": { label: "Proposition de l'IA", tone: "accent" },
  "priority.computed": { label: "Priorité calculée (règles)", tone: "neutral" },
  "case.claimed": { label: "Dossier pris en charge", tone: "neutral" },
  "case.released": { label: "Dossier libéré", tone: "neutral" },
  "human.accepted": { label: "Proposition acceptée", tone: "ok" },
  "human.edited": { label: "Proposition corrigée", tone: "high" },
  "human.rejected": { label: "Proposition rejetée", tone: "urgent" },
  "case.closed": { label: "Dossier clôturé", tone: "neutral" },
  "ai.failed": { label: "Analyse IA en échec", tone: "urgent" },
  "ai.reanalysis_requested": { label: "Nouvelle analyse demandée", tone: "accent" },
  "config.changed": { label: "Configuration IA modifiée", tone: "high" },
  "assumption.updated": { label: "Hypothèse modifiée", tone: "high" },
  "eval.started": { label: "Évaluation lancée", tone: "accent" },
  "retention.purged": { label: "Textes originaux purgés", tone: "ok" },
  "source.created": { label: "IA externe branchée", tone: "high" },
  "source.updated": { label: "IA externe modifiée", tone: "high" },
  "champion.changed": { label: "Changement de champion IA", tone: "high" },
  "crisis.started": { label: "Événement climatique déclaré", tone: "urgent" },
  "crisis.ended": { label: "Événement climatique clôturé", tone: "neutral" },
  "report.generated": { label: "Rapport de supervision généré", tone: "neutral" },
};

/** "human:sophie (gestionnaire)" -> { kind: "human", text: "sophie · gestionnaire" } */
export function actorText(actor: string): { kind: "human" | "ai" | "system"; text: string } {
  const [kind, rest = ""] = actor.split(/:(.*)/s);
  if (kind === "human") return { kind: "human", text: rest.replace(/ \((.*)\)$/, " · $1") };
  if (kind === "ai") return { kind: "ai", text: `IA · ${rest}` };
  const names: Record<string, string> = {
    intake: "réception", worker: "worker d'analyse", rules: "moteur de règles", retention: "purge",
  };
  return { kind: "system", text: `Système · ${names[rest] ?? rest}` };
}
