/** Domain badges: one vocabulary for priority, deadline, analysis state and category everywhere. */
import {
  AlertTriangle,
  CircleHelp as IconQuestion,
  Clock,
  Clock3,
  FileWarning,
  FileX2,
  House,
  Loader2,
  Lock,
  Mail,
  MessageSquareWarning,
  Paperclip,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import type { Schemas } from "@/api/client";
import { slaText } from "@/lib/time";
import { Badge, type Tone } from "./ui";

const PRIORITY: Record<string, { label: string; tone: Tone }> = {
  urgente: { label: "Urgente", tone: "urgent" },
  haute: { label: "Haute", tone: "high" },
  normale: { label: "Normale", tone: "neutral" },
  basse: { label: "Basse", tone: "neutral" },
};

export function PriorityBadge({ priority, reasons }: { priority: string | null; reasons?: string[] }) {
  if (!priority) {
    return (
      <Badge tone="neutral" title="Bras témoin : pas de tri par l'IA">
        Sans tri
      </Badge>
    );
  }
  const p = PRIORITY[priority] ?? { label: priority, tone: "neutral" as Tone };
  return (
    <Badge tone={p.tone} title={reasons?.join("\n")}>
      {p.label}
    </Badge>
  );
}

export function SlaBadge({ sla }: { sla: Schemas["SlaOut"] }) {
  if (sla.state === "termine") return null;
  const tone: Tone = sla.state === "en_retard" ? "urgent" : sla.state === "bientot" ? "high" : "neutral";
  return (
    <Badge tone={tone} title={`Délai cible : ${sla.target_hours} h`}>
      <Clock size={11} aria-hidden /> {slaText(sla.minutes_left, sla.state)}
    </Badge>
  );
}

export function AnalysisBadge({ status }: { status: string }) {
  if (status === "pending" || status === "running") {
    return (
      <Badge tone="accent">
        <Loader2 size={11} className="animate-spin" aria-hidden /> Analyse IA…
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge tone="high">
        <AlertTriangle size={11} aria-hidden /> Analyse échouée
      </Badge>
    );
  }
  return null;
}

export function HolderBadge({ holder, me }: { holder: string | null; me?: string }) {
  if (!holder) return null;
  return (
    <Badge tone={holder === me ? "accent" : "neutral"}>
      <Lock size={11} aria-hidden /> {holder === me ? "Vous" : holder}
    </Badge>
  );
}

export function confidenceLabel(c: number): { label: string; tone: Tone } {
  if (c >= 0.85) return { label: "Confiance élevée", tone: "ok" };
  if (c >= 0.6) return { label: "Confiance moyenne", tone: "neutral" };
  return { label: "Confiance faible", tone: "high" };
}

/** One icon and pastel tile per e-mail category, so the queue can be scanned at a glance. */
export const CATEGORY_LOOK: Record<string, { icon: LucideIcon; tile: string }> = {
  declaration_sinistre: { icon: FileWarning, tile: "bg-p-sky text-accent" },
  pieces_justificatives: { icon: Paperclip, tile: "bg-p-lavender text-accent" },
  relance_delai: { icon: Clock3, tile: "bg-p-cream text-high" },
  reclamation: { icon: MessageSquareWarning, tile: "bg-p-rose text-urgent" },
  demande_avance_relogement: { icon: House, tile: "bg-p-rose text-urgent" },
  resiliation: { icon: FileX2, tile: "bg-surface text-muted" },
  question_garantie: { icon: IconQuestion, tile: "bg-p-mint text-ok" },
  verification_authenticite: { icon: ShieldAlert, tile: "bg-p-cream text-high" },
  autre: { icon: Mail, tile: "bg-surface text-muted" },
};

export function CategoryTile({ category, size = 40 }: { category: string | null; size?: number }) {
  const look = (category && CATEGORY_LOOK[category]) || { icon: Mail, tile: "bg-surface text-muted" };
  const Icon = look.icon;
  return (
    <span className={`grid shrink-0 place-items-center rounded-2xl ${look.tile}`} style={{ width: size, height: size }} aria-hidden>
      <Icon size={Math.round(size * 0.48)} />
    </span>
  );
}
