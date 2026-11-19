import { Link } from "@tanstack/react-router";
import { Bot, CheckCircle2, Clock, Copy, FileText, RotateCcw, Scale, Settings2, User, XCircle } from "lucide-react";
import { useState } from "react";
import type { CaseDetail, Meta } from "@/api/client";
import { usePlaybook, usePolicy, useRelated, useTimeline } from "@/api/hooks";
import { CategoryTile } from "@/components/status";
import { toast } from "@/components/toast";
import { Badge, Button, Card, Notice, Skeleton, Tabs } from "@/components/ui";
import { actorText, EVENT_LABELS } from "@/lib/events";
import { cn, formatDate, formatEur } from "@/lib/utils";
import type { FieldValue, ReviewState } from "./reviewModel";

type Tab = "todo" | "contract" | "history" | "reply";

const str = (v: FieldValue | undefined) => (typeof v === "string" && v.trim() ? v.trim() : null);
const bool = (v: FieldValue | undefined) => (typeof v === "boolean" ? v : null);

/** What the context column and the case header both derive from the form (queries are shared). */
export function useCaseContext(id: number, state: ReviewState) {
  const f = state.fields;
  const category = (state.category.value as string) || "";
  const contract = str(f.numero_contrat?.value);
  const damage = str(f.type_dommage?.value);
  const vehicle = Boolean(str(f.immatriculation?.value)) || category === "accident_auto";
  const playbook = usePlaybook({
    category,
    numero_contrat: contract,
    type_dommage: damage,
    besoin_relogement: bool(f.besoin_relogement?.value),
    fuite_active: bool(f.fuite_active?.value),
    personne_vulnerable: bool(f.personne_vulnerable?.value),
  });
  const related = useRelated(id, contract);
  return { category, contract, damage, vehicle, playbook, related };
}

/**
 * Column 3: what the handler needs around the e-mail, one question per tab.
 * Everything here follows the form (column 2): correct a value and the to-do list,
 * the contract and the reply update. None of it is the AI: team rules and the register.
 */
export function ContextPanel({ detail, meta, state }: { detail: CaseDetail; meta: Meta; state: ReviewState }) {
  const [tab, setTab] = useState<Tab>("todo");
  const { category, contract, damage, vehicle, playbook, related } = useCaseContext(detail.id, state);

  return (
    <Card className="flex flex-col self-start">
      <div className="border-b border-line px-4 py-3">
        <Tabs<Tab>
          fill
          value={tab}
          onChange={setTab}
          items={[
            { value: "todo", label: "À faire", count: playbook.data?.steps.length },
            { value: "contract", label: "Contrat" },
            { value: "history", label: "Historique" },
            { value: "reply", label: "Réponse" },
          ]}
        />
      </div>
      <div className="px-6 py-5" role="tabpanel">
        {!category ? (
          <p className="text-sm text-muted">Choisissez une catégorie.</p>
        ) : tab === "todo" ? (
          <TodoTab playbook={playbook.data} loading={playbook.isLoading} />
        ) : tab === "contract" ? (
          <ContractTab contract={contract} vehicle={vehicle} damage={damage} meta={meta} />
        ) : tab === "history" ? (
          <HistoryTab id={detail.id} related={related.data} loading={related.isLoading} />
        ) : (
          <ReplyTab key={category} subject={playbook.data?.reply_subject} body={playbook.data?.reply_body} />
        )}
      </div>
    </Card>
  );
}

function TodoTab({ playbook, loading }: { playbook: ReturnType<typeof usePlaybook>["data"]; loading: boolean }) {
  if (loading || !playbook) return <Skeleton className="h-40" />;
  return (
    <div className="space-y-5">
      <ol className="space-y-2">
        {playbook.steps.map((s, i) => (
          <li key={i} title={s.why}
              className={cn("flex items-start gap-3 rounded-2xl px-3.5 py-3", s.urgent ? "bg-urgent-soft" : "bg-surface")}>
            <span className={cn("mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold",
              s.urgent ? "bg-urgent text-white" : "bg-white text-muted")}>{i + 1}</span>
            <div className="min-w-0">
              <div className="text-[15px] font-semibold leading-snug">{s.label}</div>
              {s.deadline && (
                <div className={cn("mt-1 inline-flex items-center gap-1 text-sm", s.urgent ? "text-urgent" : "text-high")}>
                  <Clock size={13} aria-hidden /> {s.deadline}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {playbook.frames.map((fr) => (
        <div key={fr.name} className="flex items-start gap-2.5 text-sm" title={fr.summary}>
          <Scale size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
          <div>
            <div className="font-semibold">{fr.name}</div>
            {fr.deadlines.length > 0 && <div className="text-muted">{fr.deadlines.join(" · ")}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ContractTab({ contract, vehicle, damage, meta }: {
  contract: string | null;
  vehicle: boolean;
  damage: string | null;
  meta: Meta;
}) {
  const policy = usePolicy(contract, vehicle, damage);
  if (!contract) {
    return (
      <Notice tone="high" icon={<FileText size={15} aria-hidden />}>
        Aucun n° de contrat dans l'e-mail.
      </Notice>
    );
  }
  if (policy.isLoading) return <Skeleton className="h-40" />;
  const p = policy.data;
  if (!p) return <Notice tone="high">Contrat {contract} introuvable.</Notice>;

  const damageLabel = damage ? meta.damages[damage] ?? damage : null;
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-base font-bold">{p.product} · {p.formula}</div>
          <div className="text-sm text-muted">N° {p.number} · depuis {new Date(p.since).toLocaleDateString("fr-FR")}</div>
        </div>
        <div className="flex gap-1.5">
          <Badge tone={p.status === "actif" ? "ok" : "urgent"}>{p.status}</Badge>
          {p.simulated && <Badge title="Registre fictif généré pour la démo">simulé</Badge>}
        </div>
      </div>

      {damageLabel && p.covers_damage !== null && (
        <Notice tone={p.covers_damage ? "ok" : "urgent"}
                icon={p.covers_damage ? <CheckCircle2 size={15} aria-hidden /> : <XCircle size={15} aria-hidden />}>
          {p.covers_damage
            ? <><strong>{damageLabel} : couvert</strong> · franchise {formatEur(p.deductible_eur, 0)}</>
            : <><strong>{damageLabel} : non couvert</strong> par cette formule</>}
        </Notice>
      )}

      <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {p.guarantees.map((g) => (
          <li key={g.code} className={cn("flex items-center gap-2 rounded-xl px-3 py-2 text-sm", g.included ? "bg-ok-soft" : "bg-surface text-muted line-through decoration-muted/40")}>
            {g.included ? <CheckCircle2 size={13} className="text-ok" aria-hidden /> : <XCircle size={13} aria-hidden />}
            {g.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function HistoryTab({ id, related, loading }: {
  id: number;
  related: ReturnType<typeof useRelated>["data"];
  loading: boolean;
}) {
  const timeline = useTimeline(id);
  return (
    <div className="space-y-5">
      <section>
        <div className="mb-2 text-sm font-semibold text-muted">
          Autres dossiers du client
        </div>
        {loading ? <Skeleton className="h-16" /> : !related?.length ? (
          <p className="text-sm text-muted">Aucun : premier contact.</p>
        ) : (
          <ul className="space-y-1.5">
            {related.map((r) => (
              <li key={r.id}>
                <Link to="/dossier/$id" params={{ id: String(r.id) }}
                      className="flex items-center gap-3 rounded-2xl px-2 py-1.5 hover:bg-surface">
                  <CategoryTile category={r.category} size={32} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{r.subject}</span>
                    <span className="text-sm text-muted">{formatDate(r.queued_at)}</span>
                  </span>
                  <Badge tone={r.status === "nouveau" ? "accent" : "neutral"}>{r.status === "nouveau" ? "ouvert" : r.status === "manuel" ? "manuel" : "traité"}</Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="mb-2 text-sm font-semibold text-muted">Activité</div>
        {timeline.isLoading ? <Skeleton className="h-24" /> : (
          <ol className="relative space-y-3 border-l border-line pl-5">
            {(timeline.data ?? []).map((e) => {
              const who = actorText(e.actor);
              const Icon = who.kind === "human" ? User : who.kind === "ai" ? Bot : Settings2;
              return (
                <li key={e.seq} className="relative">
                  <span className="absolute -left-[29px] grid h-5 w-5 place-items-center rounded-full border border-line bg-white">
                    <Icon size={11} className="text-muted" aria-hidden />
                  </span>
                  <div className="text-sm font-medium">{EVENT_LABELS[e.type]?.label ?? e.type}</div>
                  <div className="text-sm text-muted">{who.text} · {formatDate(e.ts)}</div>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}

function ReplyTab({ subject, body }: { subject: string | undefined; body: string | undefined }) {
  const [draft, setDraft] = useState<string | null>(null);
  if (subject === undefined || body === undefined) return <Skeleton className="h-48" />;
  const text = draft ?? body;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`Objet : ${subject}\n\n${text}`);
      toast("Réponse copiée");
    } catch {
      toast("Copie impossible : sélectionnez le texte à la main", "error");
    }
  };
  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">{subject}</div>
      <textarea aria-label="Réponse au client" value={text} onChange={(e) => setDraft(e.target.value)} rows={12}
                className="w-full resize-y rounded-2xl border border-line bg-surface/60 p-3 text-sm leading-relaxed outline-none focus:border-accent focus:ring-2 focus:ring-accent/20" />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => void copy()}><Copy size={14} aria-hidden /> Copier</Button>
        {draft !== null && (
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}><RotateCcw size={14} aria-hidden /> Rétablir</Button>
        )}
      </div>
    </div>
  );
}
