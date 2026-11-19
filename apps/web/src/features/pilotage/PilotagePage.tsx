import { AlertTriangle, CheckCheck, Clock, Inbox, Loader2, Timer } from "lucide-react";
import { useState } from "react";
import { useAssumptions, usePilotage, useUpdateAssumption, type Pilotage } from "@/api/hooks";
import { useCan } from "@/auth/session";
import { toast } from "@/components/toast";
import {
  Badge,
  Card,
  CardHeader,
  ErrorNotice,
  inputClass,
  Kpi,
  Notice,
  PageHeader,
  PageSkeleton,
} from "@/components/ui";
import { cn, formatEur, formatPct } from "@/lib/utils";
import { CrisisCard } from "./CrisisCard";

const PRIORITIES = [
  { key: "urgente", label: "Urgente", bar: "bg-urgent" },
  { key: "haute", label: "Haute", bar: "bg-high" },
  { key: "normale", label: "Normale", bar: "bg-accent" },
  { key: "basse", label: "Basse", bar: "bg-muted" },
  { key: "non_triee", label: "Sans tri (témoin)", bar: "bg-line" },
];

export function PilotagePage() {
  const p = usePilotage();
  if (p.isLoading) return <PageSkeleton />;
  if (p.error) return <ErrorNotice error={p.error} />;
  const d = p.data!;
  const { ai, control } = d.ai_value.arms;
  const maxStock = Math.max(1, ...Object.values(d.stock.by_priority));

  return (
    <div className="space-y-5">
      <PageHeader
        title="Pilotage"
      />

      {d.stock.waiting_analysis > 0 && (
        <Notice tone="accent" icon={<Loader2 size={15} className="animate-spin" />}>
          {d.stock.waiting_analysis} e-mail(s) en cours d'analyse par l'IA.
        </Notice>
      )}
      {d.stock.analysis_failed > 0 && (
        <Notice tone="high" icon={<AlertTriangle size={15} />}>
          {d.stock.analysis_failed} analyse(s) en échec après plusieurs tentatives : à traiter
          sans proposition, et à signaler à l'équipe IA.
        </Notice>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="À traiter" value={d.stock.open} pastel="lavender" icon={<Inbox size={17} aria-hidden />}
             hint={`dont ${d.stock.by_priority.urgente ?? 0} urgente(s)`} />
        <Kpi label="En retard sur le délai cible" value={d.stock.late} icon={<Clock size={17} aria-hidden />}
             tone={d.stock.late > 0 ? "urgent" : undefined} pastel="cream"
             hint={`${d.stock.due_soon} à échéance proche`} />
        <Kpi label="Traités aujourd'hui" value={d.flow.closed_today} pastel="mint" icon={<CheckCheck size={17} aria-hidden />}
             hint={`dans les délais : ${formatPct(d.flow.within_target_rate)}`} />
        <Kpi
          label="Temps gagné par dossier grâce à l'IA"
          pastel="sky"
          icon={<Timer size={17} aria-hidden />}
          value={d.ai_value.seconds_saved_per_case !== null ? `${d.ai_value.seconds_saved_per_case} s` : "—"}
          tone={d.ai_value.enough_data ? "ok" : undefined}
          hint={d.ai_value.enough_data ? "mesuré : médiane sans IA − avec IA"
            : `à mesurer : ${d.ai_value.min_per_arm} dossiers minimum par groupe`}
        />
      </div>

      <CrisisCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Stock par priorité" hint="Délai cible de traitement entre parenthèses" />
          <ul className="space-y-3 px-5 py-4">
            {PRIORITIES.map(({ key, label, bar }) => {
              const n = d.stock.by_priority[key] ?? 0;
              const late = d.stock.late_by_priority[key] ?? 0;
              const target = d.sla_targets_hours[key === "non_triee" ? "normale" : key];
              return (
                <li key={key}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>
                      {label} <span className="text-xs text-muted">({target} h)</span>
                    </span>
                    <span className="tabular-nums">
                      <strong>{n}</strong>
                      {late > 0 && <span className="ml-2 text-xs text-urgent">{late} en retard</span>}
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-surface">
                    <div className={cn("h-2 rounded-full", bar)} style={{ width: `${(n / maxStock) * 100}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card>
          <CardHeader
            title="Valeur de l'IA, mesurée"
            hint="Même équipe, mêmes e-mails : la moitié avec proposition de l'IA, l'autre sans."
          >
            <Badge tone="ok">mesuré</Badge>
          </CardHeader>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="px-5 py-2 font-medium" />
                <th className="px-3 py-2 font-medium">Avec IA</th>
                <th className="px-5 py-2 font-medium">Sans IA (témoin)</th>
              </tr>
            </thead>
            <tbody>
              <Row label="Dossiers traités" a={ai.n} b={control.n} />
              <Row label="Temps médian par dossier"
                   a={ai.median_seconds !== null ? `${ai.median_seconds} s` : "—"}
                   b={control.median_seconds !== null ? `${control.median_seconds} s` : "—"} />
              <Row label="Bonne catégorie (vs vérité terrain)"
                   a={formatPct(ai.category_accuracy)} b={formatPct(control.category_accuracy)} />
            </tbody>
          </table>
          <div className="grid grid-cols-2 gap-3 border-t border-line px-5 py-3.5 text-sm">
            <div>
              <div className="text-xs text-muted">Propositions validées sans correction</div>
              <div className="font-semibold">{formatPct(d.ai_value.accepted_as_is_rate)}</div>
            </div>
            <div>
              <div className="text-xs text-muted">Coût IA par e-mail</div>
              <div className="font-semibold">{formatEur(d.ai_value.cost_eur_per_email, 5)}</div>
            </div>
          </div>
        </Card>
      </div>

      <Projection estimate={d.estimate} />
    </div>
  );
}

function Row({ label, a, b }: { label: string; a: React.ReactNode; b: React.ReactNode }) {
  return (
    <tr className="border-t border-line">
      <td className="px-5 py-2.5 text-muted">{label}</td>
      <td className="px-3 py-2.5 font-semibold tabular-nums">{a}</td>
      <td className="px-5 py-2.5 tabular-nums">{b}</td>
    </tr>
  );
}

function Projection({ estimate }: { estimate: Pilotage["estimate"] }) {
  const assumptions = useAssumptions();
  const update = useUpdateAssumption();
  const canEdit = useCan("assumptions.write");
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  return (
    <Card>
      <CardHeader
        title="Projection mensuelle"
        hint="Calculée à partir du gain mesuré et d'hypothèses que vous pouvez modifier."
      >
        <Badge tone="high">hypothèses</Badge>
      </CardHeader>
      <div className="grid gap-5 px-5 py-4 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          {(assumptions.data ?? []).map((a) => (
            <label key={a.key} className="block text-sm">
              <span className="text-xs text-muted">
                {a.label} ({a.unit})
              </span>
              <input
                className={cn(inputClass, "mt-1")}
                type="number"
                min={0}
                disabled={!canEdit}
                value={drafts[a.key] ?? String(a.value)}
                onChange={(e) => setDrafts((x) => ({ ...x, [a.key]: e.target.value }))}
                onBlur={() => {
                  const v = Number(drafts[a.key]);
                  if (drafts[a.key] !== undefined && Number.isFinite(v) && v !== a.value) {
                    update.mutate({ key: a.key, value: v }, { onSuccess: () => toast("Hypothèse mise à jour (tracée dans le journal)") });
                  }
                }}
              />
            </label>
          ))}
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Kpi label="Heures gagnées / mois" value={estimate.monthly_hours_saved ?? "—"} />
            <Kpi label="Valeur / mois" value={formatEur(estimate.monthly_value_eur, 0)} />
            <Kpi label="Coût IA / mois" value={formatEur(estimate.monthly_model_cost_eur, 2)} />
          </div>
          <p className="text-xs text-muted">Formule : {estimate.formula}</p>
          <Notice tone="high" icon={<AlertTriangle size={15} />}>
            {estimate.warning}
          </Notice>
        </div>
      </div>
    </Card>
  );
}
