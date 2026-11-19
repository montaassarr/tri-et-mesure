import { InfoTip } from "@/components/InfoTip";
import { Copy, Crown, Ghost, KeyRound, Plug } from "lucide-react";
import { useState } from "react";
import { useAlerts, useCreateSource, useSetChampion, useSources, useToggleSource } from "@/api/hooks";
import { useCan } from "@/auth/session";
import { toast } from "@/components/toast";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorNotice,
  inputClass,
  Notice,
  PageSkeleton,
  type Tone,
} from "@/components/ui";
import { cn, formatEur, formatPct } from "@/lib/utils";

const SEVERITY_TONE: Record<string, Tone> = { critique: "urgent", attention: "high", info: "neutral" };

/** Drift and health alerts, shown on top of every AI-team tab. */
export function AlertsBar() {
  const alerts = useAlerts();
  if (!alerts.data?.length) return null;
  return (
    <div className="space-y-2">
      {alerts.data.map((a) => (
        <Notice key={a.code} tone={SEVERITY_TONE[a.severity] ?? "neutral"}>
          <strong>{a.title}.</strong> {a.detail}
          <div className="mt-0.5 text-xs opacity-80">→ {a.action}</div>
        </Notice>
      ))}
    </div>
  );
}

export function SourcesTab() {
  const sources = useSources();
  const champion = useSetChampion();
  const toggle = useToggleSource();
  const canConfigure = useCan("config.write");

  if (sources.isLoading) return <PageSkeleton />;
  if (sources.error) return <ErrorNotice error={sources.error} />;
  const list = sources.data ?? [];

  return (
    <div className="space-y-4">
      <Card className="overflow-x-auto">
        <CardHeader
          title="Tour de contrôle des IA"
          hint="N'importe quelle IA peut se brancher. Une seule est montrée aux gestionnaires (champion) ; les autres tournent en fantôme sur les mêmes dossiers et sont notées."
        />
        <table className="w-full min-w-[900px] text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-5 py-2 font-medium">Source</th>
              <th className="px-3 py-2 font-medium">Propositions</th>
              <th className="px-3 py-2 font-medium" title="Dossiers du groupe témoin : l'humain a décidé sans voir d'IA">
                <span className="inline-flex items-center gap-1">Accord humain sans biais
                  <InfoTip text="Mesuré sur les dossiers du groupe témoin : le gestionnaire décide sans voir l'IA, donc sans favoriser le champion." /></span>
              </th>
              <th className="px-3 py-2 font-medium">Accord humain (tous)</th>
              <th className="px-3 py-2 font-medium">Vérité terrain</th>
              <th className="px-3 py-2 font-medium">Coût / proposition</th>
              <th className="px-3 py-2 font-medium">Latence</th>
              <th className="px-5 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.code} className={cn("border-t border-line", !s.active && "opacity-50")}>
                <td className="px-5 py-3">
                  <div className="font-medium">{s.name}</div>
                  <div className="mt-0.5 flex gap-1">
                    {s.champion ? (
                      <Badge tone="ok"><Crown size={11} aria-hidden /> champion · montré</Badge>
                    ) : (
                      <Badge><Ghost size={11} aria-hidden /> fantôme</Badge>
                    )}
                    <Badge>{s.kind === "internal" ? "interne" : "externe"}</Badge>
                  </div>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {s.suggestions}
                  <div className="text-xs text-muted">couverture {formatPct(s.coverage)}</div>
                </td>
                <td className="px-3 py-3 font-semibold tabular-nums">
                  {formatPct(s.category_agreement_unbiased)}
                  <div className="text-xs font-normal text-muted">{s.unbiased_cases} dossier(s)</div>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {formatPct(s.category_agreement)}
                  <div className="text-xs text-muted">{s.scored_cases} jugé(s)</div>
                </td>
                <td className="px-3 py-3 tabular-nums">{formatPct(s.ground_truth_accuracy)}</td>
                <td className="px-3 py-3 tabular-nums">{formatEur(s.cost_eur_per_suggestion, 5)}</td>
                <td className="px-3 py-3 tabular-nums">
                  {s.latency_p50_ms !== null ? `${s.latency_p50_ms} ms` : "—"}
                </td>
                <td className="px-5 py-3 text-right">
                  {canConfigure && !s.champion && s.active && (
                    <Button size="sm" variant="secondary" disabled={champion.isPending}
                            onClick={() => champion.mutate(s.code, { onSuccess: () => toast(`« ${s.name} » est maintenant le champion`) })}>
                      <Crown size={13} aria-hidden /> Promouvoir
                    </Button>
                  )}
                  {canConfigure && !s.champion && s.kind === "external" && (
                    <Button size="sm" variant="ghost" disabled={toggle.isPending}
                            onClick={() => toggle.mutate({ code: s.code, active: !s.active })}>
                      {s.active ? "Désactiver" : "Activer"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {canConfigure && <PlugVendor />}
    </div>
  );
}

function PlugVendor() {
  const create = useCreateSource();
  const [name, setName] = useState("Fournisseur B");
  const [created, setCreated] = useState<{ code: string; name: string; api_key: string } | null>(null);
  const command = created ? `pnpm vendor -- --key ${created.api_key} --name "${created.name}"` : "";

  return (
    <Card>
      <CardHeader
        title={<span className="inline-flex items-center gap-1.5"><Plug size={15} aria-hidden /> Brancher une IA externe</span>}
        hint="Le fournisseur reçoit une clé et le contrat d'API. Il ne voit que du texte masqué, jamais les décisions humaines."
      />
      <div className="space-y-4 px-5 py-4">
        <form className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                create.mutate(name, { onSuccess: (r) => { setCreated(r); toast("Source créée — copiez la clé maintenant"); } });
              }}>
          <label className="min-w-60 flex-1 text-sm">
            <span className="text-xs text-muted">Nom du fournisseur</span>
            <input className={cn(inputClass, "mt-1")} value={name} minLength={2} maxLength={80}
                   onChange={(e) => setName(e.target.value)} />
          </label>
          <Button type="submit" disabled={create.isPending || name.trim().length < 2}>
            <KeyRound size={15} aria-hidden /> Créer la clé
          </Button>
        </form>
        {create.error && <ErrorNotice error={create.error} />}
        {created && (
          <Notice tone="high">
            <strong>Clé de « {created.name} » — affichée une seule fois.</strong> Seule son empreinte est conservée.
            <CopyLine value={created.api_key} />
            <div className="mt-2 text-xs">Simuler ce fournisseur (dans un terminal) :</div>
            <CopyLine value={command} />
            <div className="mt-1 text-xs opacity-80">
              Ajoutez <code>--noise 0.4</code> pour un fournisseur volontairement moins bon (démo de l'alerte de dérive),
              ou <code>--engine groq</code> pour un vrai modèle Llama.
            </div>
          </Notice>
        )}
        <div className="grid gap-2 text-xs text-muted sm:grid-cols-2">
          <div className="rounded-lg bg-surface p-3">
            <div className="font-medium text-ink">1. Récupérer les dossiers</div>
            <code>GET /api/ingest/cases</code> · en-tête <code>X-API-Key</code>
          </div>
          <div className="rounded-lg bg-surface p-3">
            <div className="font-medium text-ink">2. Proposer</div>
            <code>POST /api/ingest/cases/&#123;id&#125;/suggestion</code> · même schéma que notre IA
          </div>
        </div>
      </div>
    </Card>
  );
}

function CopyLine({ value }: { value: string }) {
  return (
    <div className="mt-1.5 flex items-center gap-2">
      <code className="min-w-0 flex-1 truncate rounded bg-white/70 px-2 py-1 font-mono text-xs text-ink">{value}</code>
      <Button size="sm" variant="secondary"
              onClick={() => navigator.clipboard?.writeText(value).then(() => toast("Copié"), () => toast("Copie impossible", "error"))}>
        <Copy size={13} aria-hidden /> Copier
      </Button>
    </div>
  );
}
