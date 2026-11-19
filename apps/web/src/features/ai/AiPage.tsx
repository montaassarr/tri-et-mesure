import { Play, RefreshCw, Trophy } from "lucide-react";
import { Fragment, useState } from "react";
import type { EvalRun } from "@/api/client";
import {
  useAIConfig,
  useEvalRuns,
  useMeta,
  useQuality,
  useReanalyze,
  useStartEval,
  useUpdateAIConfig,
} from "@/api/hooks";
import { useCan } from "@/auth/session";
import { toast } from "@/components/toast";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorNotice,
  Kpi,
  Notice,
  PageHeader,
  PageSkeleton,
  selectClass,
  Tabs,
} from "@/components/ui";
import { cn, formatDate, formatEur, formatPct } from "@/lib/utils";
import { AlertsBar, SourcesTab } from "./SourcesTab";

type Provider = "rules" | "anthropic" | "openai_compat";
const PROVIDER_LABELS: Record<Provider, string> = {
  rules: "Règles (sans IA, gratuit)",
  anthropic: "Claude (Anthropic)",
  openai_compat: "Compatible OpenAI (Groq, Mistral…)",
};

export function AiPage() {
  const [tab, setTab] = useState<"sources" | "config" | "eval" | "quality">("sources");
  return (
    <div className="space-y-4">
      <PageHeader
        title="Contrôle des IA"
      />
      <AlertsBar />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { value: "sources", label: "Tour de contrôle" },
          { value: "eval", label: "Examen hors ligne" },
          { value: "quality", label: "Qualité en production" },
          { value: "config", label: "Modèle interne" },
        ]}
      />
      {tab === "sources" && <SourcesTab />}
      {tab === "config" && <ConfigTab />}
      {tab === "eval" && <EvalTab />}
      {tab === "quality" && <QualityTab />}
    </div>
  );
}

// --- configuration ------------------------------------------------------------------

function ConfigTab() {
  const cfg = useAIConfig();
  const update = useUpdateAIConfig();
  const reanalyze = useReanalyze();
  const canConfigure = useCan("config.write");
  const [draft, setDraft] = useState<{ provider: Provider; model: string; prompt: string } | null>(null);

  if (cfg.isLoading) return <PageSkeleton />;
  if (cfg.error) return <ErrorNotice error={cfg.error} />;
  const c = cfg.data!;
  const d = draft ?? { provider: c.provider as Provider, model: c.model, prompt: c.prompt_version };
  const models = c.known_models[d.provider] ?? [];
  const changed = d.provider !== c.provider || d.model !== c.model || d.prompt !== c.prompt_version;
  const budgetPct = Math.min(100, (c.spent_today_eur / Math.max(c.daily_budget_eur, 0.0001)) * 100);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader title="En production maintenant">
          {c.overridden && <Badge tone="high">modifié à chaud</Badge>}
        </CardHeader>
        <div className="grid grid-cols-2 gap-3 px-5 py-4">
          <Kpi label="Fournisseur" value={<span className="text-lg">{PROVIDER_LABELS[c.provider as Provider] ?? c.provider}</span>} />
          <Kpi label="Modèle · prompt" value={<span className="text-lg">{c.model} · {c.prompt_version}</span>} />
          <Kpi label="En attente d'analyse" value={c.queue_depth} hint="e-mails dans la file du worker" />
          <div className="rounded-xl border border-line p-4">
            <div className="text-xs font-medium text-muted">Budget du jour</div>
            <div className="mt-1.5 text-lg font-semibold tabular-nums">
              {formatEur(c.spent_today_eur, 4)} / {formatEur(c.daily_budget_eur, 2)}
            </div>
            <div className="mt-2 h-2 rounded-full bg-surface">
              <div className={cn("h-2 rounded-full", budgetPct > 80 ? "bg-urgent" : "bg-accent")} style={{ width: `${budgetPct}%` }} />
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Changer de modèle" hint="Le changement est validé, appliqué aux nouvelles analyses et tracé dans le journal." />
        <div className="space-y-3 px-5 py-4">
          <label className="block text-sm">
            <span className="text-xs text-muted">Fournisseur</span>
            <select
              className={cn(selectClass, "mt-1 w-full")}
              value={d.provider}
              disabled={!canConfigure}
              onChange={(e) => {
                const p = e.target.value as Provider;
                setDraft({ ...d, provider: p, model: c.known_models[p]?.[0] ?? "" });
              }}
            >
              {(Object.keys(PROVIDER_LABELS) as Provider[]).map((p) => (
                <option key={p} value={p} disabled={!c.providers_available[p]}>
                  {PROVIDER_LABELS[p]} {c.providers_available[p] ? "" : "— clé absente"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-xs text-muted">Modèle</span>
            <select className={cn(selectClass, "mt-1 w-full")} value={d.model} disabled={!canConfigure || d.provider === "rules"}
                    onChange={(e) => setDraft({ ...d, model: e.target.value })}>
              {models.map((m) => {
                const price = c.prices_usd_per_mtok[m];
                return (
                  <option key={m} value={m}>
                    {m}
                    {price ? ` — ${price.input} $ / ${price.output} $ par M jetons` : ""}
                  </option>
                );
              })}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-xs text-muted">Version du prompt</span>
            <select className={cn(selectClass, "mt-1 w-full")} value={d.prompt} disabled={!canConfigure}
                    onChange={(e) => setDraft({ ...d, prompt: e.target.value })}>
              {c.prompt_versions.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <Notice tone="neutral">Conseil : lancez d'abord une évaluation hors ligne de ce modèle.</Notice>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={!changed || update.isPending}
              onClick={() =>
                update.mutate(
                  { provider: d.provider, model: d.provider === "rules" ? null : d.model, prompt_version: d.prompt },
                  { onSuccess: () => { setDraft(null); toast("Configuration appliquée"); } },
                )
              }
            >
              Appliquer
            </Button>
            <Button
              variant="secondary"
              disabled={reanalyze.isPending}
              onClick={() => reanalyze.mutate(undefined, { onSuccess: (n) => toast(`${n} dossier(s) renvoyé(s) en analyse`) })}
              title="Les dossiers ouverts seront réanalysés avec la configuration actuelle"
            >
              <RefreshCw size={15} aria-hidden /> Réanalyser les dossiers ouverts
            </Button>
          </div>
          {update.error && <ErrorNotice error={update.error} />}
        </div>
      </Card>
    </div>
  );
}

// --- offline evaluation -------------------------------------------------------------

function EvalTab() {
  const runs = useEvalRuns();
  const cfg = useAIConfig();
  const start = useStartEval();
  const meta = useMeta();
  const canRun = useCan("eval.run");
  const [provider, setProvider] = useState<Provider>("rules");
  const [model, setModel] = useState("rules-v1");
  const [dataset, setDataset] = useState<"ci" | "dev" | "test">("test");
  const [selected, setSelected] = useState<number | null>(null);

  if (runs.isLoading || cfg.isLoading) return <PageSkeleton />;
  if (runs.error) return <ErrorNotice error={runs.error} />;
  const list = runs.data ?? [];
  const done = list.filter((r) => r.status === "done");
  const best = done.reduce<EvalRun | null>(
    (b, r) => (!b || (r.summary.macro_f1 as number) > (b.summary.macro_f1 as number) ? r : b),
    null,
  );
  const current = list.find((r) => r.id === selected) ?? done[0];
  const c = cfg.data!;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Faire passer l'examen à un modèle"
                    hint="E-mails fictifs à réponse connue, même chemin que la production (masquage, modèle, contrôle du format)." />
        <div className="flex flex-wrap items-end gap-3 px-5 py-4">
          <label className="text-xs text-muted">
            Fournisseur
            <select className={cn(selectClass, "mt-1 block")} value={provider}
                    onChange={(e) => { const p = e.target.value as Provider; setProvider(p); setModel(c.known_models[p]?.[0] ?? ""); }}>
              {(Object.keys(PROVIDER_LABELS) as Provider[]).map((p) => (
                <option key={p} value={p} disabled={!c.providers_available[p]}>{PROVIDER_LABELS[p]}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted">
            Modèle
            <select className={cn(selectClass, "mt-1 block")} value={model} onChange={(e) => setModel(e.target.value)}>
              {(c.known_models[provider] ?? []).map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
          <label className="text-xs text-muted">
            Jeu de test
            <select className={cn(selectClass, "mt-1 block")} value={dataset}
                    onChange={(e) => setDataset(e.target.value as "ci" | "dev" | "test")}>
              <option value="test">test — 80 e-mails jamais vus</option>
              <option value="dev">dev — 40 e-mails</option>
              <option value="ci">ci — 30 e-mails (rapide)</option>
            </select>
          </label>
          <Button disabled={!canRun || start.isPending}
                  onClick={() => start.mutate({ provider, model: provider === "openai_compat" ? null : model, dataset },
                                              { onSuccess: () => toast("Évaluation lancée") })}>
            <Play size={15} aria-hidden /> Lancer
          </Button>
          {provider !== "rules" && <span className="text-xs text-muted">Appels payants</span>}
        </div>
        {start.error && <div className="px-5 pb-4"><ErrorNotice error={start.error} /></div>}
      </Card>

      <Card className="overflow-x-auto">
        <CardHeader title="Classement" hint="Macro-F1 : qualité moyenne sur les 9 catégories (1 = parfait)." />
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-5 py-2 font-medium">Modèle</th>
              <th className="px-3 py-2 font-medium">Jeu</th>
              <th className="px-3 py-2 font-medium">Macro-F1</th>
              <th className="px-3 py-2 font-medium">Champs (F1)</th>
              <th className="px-3 py-2 font-medium">Format valide</th>
              <th className="px-3 py-2 font-medium">€ / 1000 e-mails</th>
              <th className="px-3 py-2 font-medium">Latence p50</th>
              <th className="px-5 py-2 font-medium">Date</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r) => {
              const s = r.summary as Record<string, number>;
              return (
                <tr key={r.id} onClick={() => setSelected(r.id)}
                    className={cn("cursor-pointer border-t border-line hover:bg-surface", current?.id === r.id && "bg-accent-soft/40")}>
                  <td className="px-5 py-2.5 font-medium">
                    {r.model}
                    {best?.id === r.id && <Badge tone="ok" className="ml-2"><Trophy size={11} aria-hidden /> meilleur</Badge>}
                    {r.status === "running" && <Badge tone="accent" className="ml-2">en cours</Badge>}
                    {r.status === "error" && <Badge tone="urgent" className="ml-2">erreur</Badge>}
                  </td>
                  <td className="px-3 py-2.5">{r.dataset}</td>
                  <td className="px-3 py-2.5 font-semibold tabular-nums">{s.macro_f1?.toFixed(3) ?? "—"}</td>
                  <td className="px-3 py-2.5 tabular-nums">{s.field_micro_f1?.toFixed(3) ?? "—"}</td>
                  <td className="px-3 py-2.5 tabular-nums">{formatPct(s.schema_valid_rate)}</td>
                  <td className="px-3 py-2.5 tabular-nums">{s.cost_eur_per_email !== undefined ? formatEur(s.cost_eur_per_email * 1000, 3) : "—"}</td>
                  <td className="px-3 py-2.5 tabular-nums">{s.latency_p50_ms !== undefined ? `${s.latency_p50_ms} ms` : "—"}</td>
                  <td className="whitespace-nowrap px-5 py-2.5 text-muted">{formatDate(r.created_at)}</td>
                </tr>
              );
            })}
            {list.length === 0 && (
              <tr><td colSpan={8} className="px-5 py-10 text-center text-muted">Aucune évaluation. Lancez-en une ci-dessus.</td></tr>
            )}
          </tbody>
        </table>
      </Card>

      {current?.status === "error" && <Notice tone="urgent">{current.error}</Notice>}
      {current?.status === "done" && <RunDetail run={current} labels={meta.data?.categories ?? {}} />}
    </div>
  );
}

interface PRF { precision: number; recall: number; f1: number; tp: number; fn: number }

function RunDetail({ run, labels }: { run: EvalRun; labels: Record<string, string> }) {
  const report = run.report as {
    per_category: Record<string, PRF>;
    confusion: Record<string, Record<string, number>>;
  };
  const cats = Object.keys(report.confusion ?? {});
  const max = Math.max(1, ...cats.flatMap((c) => Object.values(report.confusion[c] ?? {})));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="overflow-x-auto">
        <CardHeader title={`Détail par catégorie — ${run.model}`} hint="P : précision · R : rappel" />
        <table className="w-full text-sm">
          <tbody>
            {Object.entries(report.per_category).map(([cat, m]) => (
              <tr key={cat} className="border-t border-line">
                <td className="px-5 py-1.5">{labels[cat] ?? cat}</td>
                <td className="px-2 py-1.5 tabular-nums text-muted">P {m.precision.toFixed(2)}</td>
                <td className="px-2 py-1.5 tabular-nums text-muted">R {m.recall.toFixed(2)}</td>
                <td className={cn("px-5 py-1.5 font-semibold tabular-nums", m.f1 < 0.7 && "text-urgent")}>{m.f1.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card className="overflow-x-auto">
        <CardHeader title="Confusions" hint="Lignes : réponse attendue · colonnes : réponse du modèle" />
        <div className="px-5 py-4">
          <table className="text-xs">
            <tbody>
              <tr>
                <td />
                {cats.map((c) => <td key={c} className="px-1 pb-1 text-center text-muted" title={labels[c]}>{c.slice(0, 4)}</td>)}
              </tr>
              {cats.map((row) => (
                <tr key={row}>
                  <td className="pr-2 text-right text-muted" title={labels[row]}>{labels[row]?.slice(0, 22) ?? row}</td>
                  {cats.map((col) => {
                    const v = report.confusion[row]?.[col] ?? 0;
                    const a = v / max;
                    return (
                      <Fragment key={col}>
                        <td className="h-7 w-8 border border-white text-center tabular-nums"
                            style={{
                              background: row === col ? `rgba(6,118,71,${0.12 + a * 0.7})` : v ? `rgba(180,35,24,${0.15 + a * 0.7})` : "#f6f8fb",
                              color: a > 0.5 ? "white" : undefined,
                            }}>
                          {v || ""}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// --- production quality -------------------------------------------------------------

function QualityTab() {
  const q = useQuality();
  const meta = useMeta();
  if (q.isLoading) return <PageSkeleton />;
  if (q.error) return <ErrorNotice error={q.error} />;
  const d = q.data!;
  const labels: Record<string, string> = { category: "Catégorie", ...(meta.data?.fields ?? {}) };
  const reasons = meta.data?.reason_codes ?? {};

  if (d.reviews === 0) {
    return <Notice tone="neutral">Aucun dossier du groupe IA n'a encore été traité : la qualité en production apparaîtra ici.</Notice>;
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Dossiers jugés" value={d.reviews} />
        <Kpi label="Réponses au bon format" value={formatPct(d.calls.schema_valid_rate)} hint={`repli sur règles : ${formatPct(d.calls.fallback_rate)}`} />
        <Kpi label="Latence p50 / p95" value={d.calls.latency_p50_ms !== null ? `${d.calls.latency_p50_ms} ms` : "—"}
             hint={d.calls.latency_p95_ms !== null ? `p95 : ${d.calls.latency_p95_ms} ms` : "pas d'appel modèle"} />
        <Kpi label="Coût total" value={formatEur(d.calls.cost_eur_total, 4)} hint={`${d.calls.model_calls} appel(s) modèle`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="Ce que les gestionnaires font des propositions" hint="Un champ souvent corrigé = une piste d'amélioration du prompt." />
          <ul className="space-y-2.5 px-5 py-4">
            {Object.entries(d.per_item).map(([item, c]) => {
              const total = c.accepted + c.edited + c.rejected || 1;
              return (
                <li key={item} className="text-sm">
                  <div className="flex justify-between">
                    <span>{labels[item] ?? item}</span>
                    <span className="text-xs text-muted">{formatPct(c.accepted / total)} acceptés</span>
                  </div>
                  <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-surface" aria-hidden>
                    <div className="bg-ok" style={{ width: `${(c.accepted / total) * 100}%` }} />
                    <div className="bg-high" style={{ width: `${(c.edited / total) * 100}%` }} />
                    <div className="bg-urgent" style={{ width: `${(c.rejected / total) * 100}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="flex gap-4 border-t border-line px-5 py-2.5 text-xs text-muted">
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-ok" />accepté</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-high" />corrigé</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-urgent" />rejeté</span>
          </div>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader title="Par modèle et version du prompt" />
            <ul className="divide-y divide-line text-sm">
              {Object.entries(d.by_model_and_prompt).map(([k, v]) => (
                <li key={k} className="flex justify-between px-5 py-2.5">
                  <span>{k}</span>
                  <span className="text-muted">{v.n} dossiers · catégorie acceptée {formatPct(v.category_acceptance_rate)}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Motifs de rejet" />
            <ul className="divide-y divide-line text-sm">
              {Object.keys(d.rejection_reasons).length === 0 && <li className="px-5 py-2.5 text-muted">Aucun rejet.</li>}
              {Object.entries(d.rejection_reasons).map(([k, n]) => (
                <li key={k} className="flex justify-between px-5 py-2.5">
                  <span>{reasons[k] ?? k}</span>
                  <strong className="tabular-nums">{n}</strong>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
