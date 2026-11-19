import { Link } from "@tanstack/react-router";
import { ArrowLeft, Printer, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useMeta, useOversightReport } from "@/api/hooks";
import { Badge, Button, Card, ErrorNotice, Notice, PageSkeleton, Tabs } from "@/components/ui";
import { formatDate } from "@/lib/utils";
import { EVENT_LABELS } from "@/lib/events";

/** Printable human-oversight report. Generating it is itself recorded in the audit log. */
export function ReportPage() {
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const report = useOversightReport(Number(days));
  const meta = useMeta();
  const labels: Record<string, string> = { category: "Catégorie", ...(meta.data?.fields ?? {}) };
  const reasons = meta.data?.reason_codes ?? {};

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link to="/journal" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
          <ArrowLeft size={15} aria-hidden /> Journal d'audit
        </Link>
        <div className="flex items-center gap-2">
          <Tabs value={days} onChange={setDays}
                items={[{ value: "7", label: "7 jours" }, { value: "30", label: "30 jours" }, { value: "90", label: "90 jours" }]} />
          <Button onClick={() => window.print()}><Printer size={15} aria-hidden /> Imprimer / PDF</Button>
        </div>
      </div>

      {report.isLoading ? <PageSkeleton /> : report.error ? <ErrorNotice error={report.error} /> : (() => {
        const r = report.data!;
        const d = r.decisions;
        return (
          <Card className="space-y-6 p-8 print:border-0 print:p-0">
            <header>
              <h1 className="text-2xl font-semibold">Rapport de supervision humaine</h1>
              <p className="mt-1 text-sm text-muted">
                Du {formatDate(r.period.from)} au {formatDate(r.period.to)} · généré par{" "}
                {r.generated_by.replace(/^human:/, "")} · Tri &amp; Mesure (prototype, données synthétiques)
              </p>
            </header>

            <Notice tone="ok" icon={<ShieldCheck size={16} />}>{r.statement}</Notice>

            <Section title="1. Décisions">
              <Grid rows={[
                ["Dossiers clos", d.total],
                ["Clos par une personne authentifiée", `${d.by_authenticated_human} / ${d.total}`],
                ["Avec proposition de l'IA", d.with_ai_proposal],
                ["Sans IA (groupe témoin)", d.without_ai_control_arm],
                ["Propositions validées sans correction", d.ai_accepted_as_is],
                ["Envoyés en traitement manuel", d.manual_handling],
                ["Gestionnaires distincts", d.reviewers],
              ]} />
              <SubList title="Corrections humaines par élément" items={d.corrections_by_item} labels={labels} empty="Aucune correction." />
              <SubList title="Motifs de rejet" items={d.rejection_reasons} labels={reasons} empty="Aucun rejet." />
            </Section>

            <Section title="2. Systèmes d'IA utilisés">
              <SubList title="Propositions par système (source · modèle · prompt)" items={r.ai_systems.suggestions_by_system} empty="Aucune." />
              <SubList title="Propositions montrées aux gestionnaires" items={r.ai_systems.shown_to_handlers_by_system} empty="Aucune." />
              <Grid rows={[
                ["Replis automatiques sur les règles", r.ai_systems.fallbacks_to_rules],
                ["Analyses en échec", r.ai_systems.analysis_failures],
              ]} />
            </Section>

            <Section title="3. Modifications du système">
              {r.changes.length === 0 ? <p className="text-sm text-muted">Aucune modification sur la période.</p> : (
                <ul className="space-y-1 text-sm">
                  {r.changes.map((c, i) => (
                    <li key={i} className="flex flex-wrap gap-x-2">
                      <span className="text-muted">{c.ts.replace("T", " ").slice(0, 16)}</span>
                      <Badge>{EVENT_LABELS[c.type]?.label ?? c.type}</Badge>
                      <span>{c.actor.replace(/^human:/, "")}</span>
                      <span className="text-xs text-muted">{JSON.stringify(c.payload)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            <Section title="4. Protection des données">
              <Grid rows={[
                ["E-mails masqués avant l'IA", r.privacy.emails_masked],
                ["Purges de textes originaux", r.privacy.raw_text_purges],
                ["Ce que reçoivent les fournisseurs d'IA", r.privacy.what_vendors_receive],
              ]} />
            </Section>

            <Section title="5. Intégrité du journal">
              <Notice tone={r.integrity.chain_ok ? "ok" : "urgent"}
                      icon={r.integrity.chain_ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}>
                {r.integrity.chain_ok
                  ? `Chaîne intacte : ${r.integrity.events_checked} événements vérifiés, dont ${r.integrity.events_in_period} sur la période.`
                  : "Chaîne rompue : incident de sécurité à investiguer."}
              </Notice>
              <p className="mt-2 text-xs text-muted">
                Sceau du rapport — événement n° {r.integrity.seal_seq} · empreinte{" "}
                <span className="break-all font-mono">{r.integrity.seal_hash}</span>. Toute modification ultérieure du
                journal antérieur à ce sceau sera détectée par la vérification d'intégrité.
              </p>
            </Section>
          </Card>
        );
      })()}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 break-inside-avoid">
      <h2 className="border-b border-line pb-1 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Grid({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 border-b border-dashed border-line py-1">
          <dt className="text-muted">{k}</dt>
          <dd className="font-medium tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function SubList({ title, items, labels = {}, empty }: {
  title: string; items: Record<string, number>; labels?: Record<string, string>; empty: string;
}) {
  const entries = Object.entries(items);
  return (
    <div>
      <div className="text-xs font-medium text-muted">{title}</div>
      {entries.length === 0 ? <p className="text-sm text-muted">{empty}</p> : (
        <ul className="mt-1 flex flex-wrap gap-1.5">
          {entries.map(([k, n]) => <Badge key={k}>{labels[k] ?? k} · {n}</Badge>)}
        </ul>
      )}
    </div>
  );
}
