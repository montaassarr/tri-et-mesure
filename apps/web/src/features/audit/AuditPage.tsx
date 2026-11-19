import { Link } from "@tanstack/react-router";
import { Bot, Cog, FileText, ShieldAlert, ShieldCheck, User } from "lucide-react";
import { Fragment, useState } from "react";
import type { AuditEvent } from "@/api/client";
import { useAudit, useRegister, useVerifyChain, type AuditFilters } from "@/api/hooks";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorNotice,
  inputClass,
  Notice,
  PageHeader,
  PageSkeleton,
  selectClass,
  Tabs,
  type Tone,
} from "@/components/ui";
import { EVENT_LABELS } from "@/lib/events";
import { cn } from "@/lib/utils";



const SYSTEM_NAMES: Record<string, string> = {
  intake: "réception",
  worker: "worker d'analyse",
  rules: "moteur de règles",
  retention: "purge",
};

function actorView(actor: string) {
  const [kind, rest = ""] = actor.split(/:(.*)/s);
  if (kind === "human") return { icon: User, text: rest.replace(/ \((.*)\)$/, " · $1") };
  if (kind === "ai") return { icon: Bot, text: `IA · ${rest}` };
  return { icon: Cog, text: `Système · ${SYSTEM_NAMES[rest] ?? rest}` };
}

export function AuditPage() {
  const [filters, setFilters] = useState<AuditFilters>({});
  const [caseInput, setCaseInput] = useState("");
  const [openSeq, setOpenSeq] = useState<number | null>(null);
  const audit = useAudit(filters);
  const verify = useVerifyChain();

  return (
    <div className="space-y-4">
      <PageHeader
        title="Journal d'audit"
        action={
          <div className="flex flex-wrap gap-2">
            <Link to="/journal/rapport"
                  className="inline-flex h-11 items-center gap-1.5 rounded-md border border-line bg-white px-4 text-sm font-medium hover:bg-surface">
              <FileText size={16} aria-hidden /> Rapport de supervision
            </Link>
            <Button size="lg" onClick={() => verify.mutate()} disabled={verify.isPending}>
              <ShieldCheck size={18} aria-hidden /> Vérifier l'intégrité
            </Button>
          </div>
        }
      />

      {verify.data &&
        (verify.data.ok ? (
          <Notice tone="ok" icon={<ShieldCheck size={15} />}>
            Intégrité confirmée : les {verify.data.checked} événements forment une chaîne intacte.
          </Notice>
        ) : (
          <Notice tone="urgent" icon={<ShieldAlert size={15} />}>
            Chaîne rompue à l'événement n° {verify.data.first_broken_seq} : {verify.data.reason}
          </Notice>
        ))}
      {verify.error && <ErrorNotice error={verify.error} />}

      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
            <Tabs
              value={filters.actor_kind ?? "all"}
              onChange={(v) => setFilters((f) => ({ ...f, actor_kind: v === "all" ? undefined : v }))}
              items={[
                { value: "all", label: "Tous" },
                { value: "human", label: "Humains" },
                { value: "ai", label: "IA" },
                { value: "system", label: "Système" },
              ]}
            />
            <select
              className={selectClass}
              aria-label="Type d'événement"
              value={filters.type ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value || undefined }))}
            >
              <option value="">Tous les événements</option>
              {Object.entries(EVENT_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
            <form
              className="flex items-center gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                const n = Number(caseInput);
                setFilters((f) => ({ ...f, email_id: caseInput && n > 0 ? n : undefined }));
              }}
            >
              <input
                className={cn(inputClass, "w-28")}
                placeholder="Dossier n°"
                inputMode="numeric"
                value={caseInput}
                onChange={(e) => setCaseInput(e.target.value.replace(/\D/g, ""))}
                aria-label="Filtrer par numéro de dossier"
              />
            </form>
          </div>
          {audit.isLoading ? (
            <PageSkeleton />
          ) : audit.error ? (
            <div className="p-4">
              <ErrorNotice error={audit.error} />
            </div>
          ) : (
            <EventsTable events={audit.data ?? []} openSeq={openSeq} onToggle={(s) => setOpenSeq(openSeq === s ? null : s)} />
          )}
        </Card>
        <RegisterCard />
      </div>
    </div>
  );
}

function EventsTable({
  events,
  openSeq,
  onToggle,
}: {
  events: AuditEvent[];
  openSeq: number | null;
  onToggle: (seq: number) => void;
}) {
  if (events.length === 0) return <div className="px-5 py-10 text-center text-sm text-muted">Aucun événement.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="text-left text-xs text-muted">
          <tr>
            <th className="px-5 py-2 font-medium">N°</th>
            <th className="px-3 py-2 font-medium">Quand (UTC)</th>
            <th className="px-3 py-2 font-medium">Qui</th>
            <th className="px-3 py-2 font-medium">Quoi</th>
            <th className="px-5 py-2 font-medium">Dossier</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => {
            const actor = actorView(e.actor);
            const Icon = actor.icon;
            const ev = EVENT_LABELS[e.type] ?? { label: e.type, tone: "neutral" as Tone };
            const open = openSeq === e.seq;
            return (
              <Fragment key={e.seq}>
                <tr
                  className="cursor-pointer border-t border-line hover:bg-surface"
                  onClick={() => onToggle(e.seq)}
                  aria-expanded={open}
                >
                  <td className="px-5 py-2 tabular-nums text-muted">{e.seq}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-muted">
                    {e.ts.replace("T", " ").slice(0, 19)}
                  </td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-1.5 text-xs">
                      <Icon size={13} className="text-muted" aria-hidden />
                      {actor.text}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge tone={ev.tone}>{ev.label}</Badge>
                  </td>
                  <td className="px-5 py-2 tabular-nums text-muted">{e.email_id ?? "—"}</td>
                </tr>
                {open && (
                  <tr className="bg-surface">
                    <td colSpan={5} className="px-5 py-3 text-xs">
                      <pre className="whitespace-pre-wrap break-all">{JSON.stringify(e.payload, null, 2)}</pre>
                      <div className="mt-2 font-mono text-muted">
                        empreinte {e.hash}
                        <br />
                        précédente {e.prev_hash}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RegisterCard() {
  const reg = useRegister();
  if (reg.isLoading) return <Card className="h-80 animate-pulse" />;
  if (reg.error) return <ErrorNotice error={reg.error} />;
  const r = reg.data!;
  const masked = Object.entries(r.minimisation.masked_entities_total);
  return (
    <Card className="self-start">
      <CardHeader title="Registre du traitement" hint="Ce que l'outil fait des données, preuves à l'appui." />
      <dl className="space-y-3.5 px-5 py-4 text-sm">
        <Item label="Finalité">{r.purpose}</Item>
        <Item label="Décision automatisée">{r.decisions_by_ai}</Item>
        <Item label="Minimisation avant l'IA">
          <div className="flex flex-wrap gap-1">
            {masked.length === 0 ? "—" : masked.map(([k, n]) => (
              <Badge key={k} tone="ok">
                {k} ×{n}
              </Badge>
            ))}
          </div>
          <div className="mt-1 text-xs text-muted">Non masqué : {r.minimisation.not_masked.join(", ")}</div>
        </Item>
        <Item label="Destinataires">
          {r.recipients.what_they_receive}
          <div className="mt-1 text-xs text-muted">
            Fournisseurs utilisés : {r.recipients.model_providers_used.join(", ") || "aucun"}
          </div>
        </Item>
        <Item label="Conservation">
          Texte original {r.retention.raw_text_days} jours, puis effacé ({r.retention.raw_text_purged} effacé(s)).{" "}
          {r.retention.kept} conservés.
        </Item>
        <Item label="Journal">
          {r.audit.events} événements ·{" "}
          {r.audit.chain_ok ? <span className="text-ok">chaîne intacte</span> : <span className="text-urgent">chaîne rompue</span>}
        </Item>
      </dl>
    </Card>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}
