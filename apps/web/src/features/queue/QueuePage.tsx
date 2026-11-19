import { useNavigate } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, CloudLightning, Download, Flame, Inbox, Sparkles, Timer } from "lucide-react";
import { useMemo, useState } from "react";
import type { QueueItem } from "@/api/client";
import { useCases, useMeta, useNextCase, useSeed } from "@/api/hooks";
import { useCan, useSession } from "@/auth/session";
import { InfoTip } from "@/components/InfoTip";
import { AnalysisBadge, CategoryTile, HolderBadge, PriorityBadge, SlaBadge } from "@/components/status";
import { toast } from "@/components/toast";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  HighlightCard,
  Kpi,
  PageHeader,
  PageSkeleton,
  Tabs,
} from "@/components/ui";
import { ago } from "@/lib/time";
import { cn, download, toCsv } from "@/lib/utils";

type Filter = "all" | "urgente" | "haute" | "normale" | "basse" | "sans_tri" | "en_retard" | "evenement";

const FILTERS: { value: Filter; label: string; match: (c: QueueItem) => boolean }[] = [
  { value: "all", label: "Tous", match: () => true },
  { value: "en_retard", label: "En retard", match: (c) => c.sla.state === "en_retard" },
  { value: "urgente", label: "Urgente", match: (c) => c.priority === "urgente" },
  { value: "haute", label: "Haute", match: (c) => c.priority === "haute" },
  { value: "normale", label: "Normale", match: (c) => c.priority === "normale" },
  { value: "basse", label: "Basse", match: (c) => c.priority === "basse" },
  { value: "sans_tri", label: "Sans tri (témoin)", match: (c) => c.priority === null },
  { value: "evenement", label: "Événement climatique", match: (c) => c.event_id !== null },
];

export function QueuePage() {
  const cases = useCases();
  const meta = useMeta();
  const seed = useSeed();
  const next = useNextCase();
  const navigate = useNavigate();
  const me = useSession()?.user.name;
  const canReview = useCan("cases.review");
  const canSeed = useCan("demo.seed");
  const [tab, setTab] = useState<"open" | "closed">("open");
  const [filter, setFilter] = useState<Filter>("all");

  const all = useMemo(() => cases.data ?? [], [cases.data]);
  const open = all.filter((c) => c.status === "nouveau");
  const closed = all.filter((c) => c.status !== "nouveau");
  const list = (tab === "open" ? open : closed).filter(FILTERS.find((f) => f.value === filter)!.match);
  const late = open.filter((c) => c.sla.state === "en_retard").length;
  const urgent = open.filter((c) => c.priority === "urgente").length;
  // What "Traiter le suivant" will open: the most urgent free case (same rule as the server).
  const upcoming = open.find(
    (c) => (c.holder === null || c.holder === me) && !(c.arm === "ai" && (c.analysis_status === "pending" || c.analysis_status === "running")),
  );
  const categories = meta.data?.categories ?? {};

  if (cases.isLoading) return <PageSkeleton />;
  if (cases.error) return <ErrorNotice error={cases.error} />;

  if (all.length === 0) {
    return (
      <>
        <PageHeader title="Corbeille" />
        <EmptyState
          title="La corbeille est vide"
          action={
            canSeed && (
              <Button size="lg" disabled={seed.isPending}
                      onClick={() => seed.mutate(undefined, { onSuccess: (r) => toast(`${r.created} e-mails reçus, analyse IA en cours`) })}>
                <Sparkles size={18} aria-hidden />
                {seed.isPending ? "Chargement…" : "Charger 80 e-mails de démo"}
              </Button>
            )
          }
        >
          Les e-mails sont fictifs. La moitié reçoit une proposition de l'IA ; l'autre moitié est traitée sans IA, pour
          mesurer le temps réellement gagné.
        </EmptyState>
      </>
    );
  }

  async function openNext() {
    const id = await next.mutateAsync();
    if (id) navigate({ to: "/dossier/$id", params: { id: String(id) } });
    else toast("Aucun dossier disponible : tout est traité ou en cours d'analyse");
  }

  return (
    <div>
      <PageHeader
        title="Corbeille"
      />

      <div className="mb-8 grid gap-4 lg:grid-cols-[1fr_1fr_1fr_1.25fr]">
        <Kpi pastel="lavender" label="À traiter" value={open.length} icon={<Inbox size={18} aria-hidden />}
             hint={`${closed.length} déjà traité(s)`} />
        <Kpi pastel="rose" label="Urgents" value={urgent} icon={<Flame size={18} aria-hidden />} />
        <Kpi pastel="cream" label="En retard" value={late} icon={<Timer size={18} aria-hidden />} tone={late > 0 ? "urgent" : undefined} />
        {canReview ? (
          <HighlightCard
            title={upcoming ? "Votre prochain dossier" : "Rien à traiter pour l'instant"}
            action={
              <Button variant="light" size="lg" onClick={openNext} disabled={next.isPending || !upcoming}>
                Traiter le dossier suivant <ArrowRight size={17} aria-hidden />
              </Button>
            }
          >
            {upcoming ? (
              <>
                <span className="font-semibold text-white">{upcoming.subject}</span>
                <br />
                {upcoming.priority_reasons[0] ?? (upcoming.priority ? `Priorité ${upcoming.priority}` : "Dossier du groupe témoin")}
              </>
            ) : (
              "Les nouveaux e-mails arrivent ici dès leur analyse."
            )}
          </HighlightCard>
        ) : (
          <Kpi pastel="mint" label="Traités" value={closed.length} />
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-extrabold">Dossiers</h2>
          <Tabs
            value={tab}
            onChange={(v) => { setTab(v); setFilter("all"); }}
            items={[{ value: "open", label: "À traiter", count: open.length }, { value: "closed", label: "Traités", count: closed.length }]}
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filtrer">
          {FILTERS.map((f) => {
            const count = (tab === "open" ? open : closed).filter(f.match).length;
            if (f.value !== "all" && count === 0) return null;
            return (
              <button key={f.value} type="button" aria-pressed={filter === f.value} onClick={() => setFilter(f.value)}
                      className={cn("rounded-full border px-3 py-1.5 text-sm font-medium",
                        filter === f.value ? "border-accent bg-accent text-white" : "border-line bg-white text-muted hover:text-ink")}>
                {f.label} <span className="tabular-nums opacity-80">{count}</span>
              </button>
            );
          })}
          <Button variant="ghost" size="sm"
                  onClick={() => download("corbeille.csv", toCsv(list.map((c) => ({
                    id: c.id, objet: c.subject, priorite: c.priority ?? "sans tri", categorie: c.category, delai: c.sla.state, arrive: c.queued_at,
                  }))))}>
            <Download size={14} aria-hidden /> CSV
          </Button>
        </div>
      </div>

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="text-left text-sm font-semibold text-muted">
            <tr>
              <th className="px-6 py-3">E-mail</th>
              <th className="px-3 py-3">
                <span className="inline-flex items-center gap-1">Priorité <InfoTip screen="queue" name="Priorité" /></span>
              </th>
              <th className="px-3 py-3">
                <span className="inline-flex items-center gap-1">Délai <InfoTip screen="queue" name="Délai" /></span>
              </th>
              <th className="px-3 py-3">Arrivé</th>
              <th className="px-6 py-3">État</th>
            </tr>
          </thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id} tabIndex={0}
                  className="cursor-pointer border-t border-line hover:bg-surface focus:bg-surface focus:outline-none"
                  onClick={() => navigate({ to: "/dossier/$id", params: { id: String(c.id) } })}
                  onKeyDown={(e) => e.key === "Enter" && navigate({ to: "/dossier/$id", params: { id: String(c.id) } })}>
                <td className="px-6 py-3">
                  <div className="flex items-center gap-3">
                    <CategoryTile category={c.category} />
                    <div className="min-w-0">
                      <div className="max-w-[22rem] truncate font-semibold">{c.subject}</div>
                      <div className="max-w-[22rem] truncate text-sm text-muted">
                        {c.category ? categories[c.category] ?? c.category : "Groupe témoin"}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <PriorityBadge priority={c.priority} reasons={c.priority_reasons} />
                </td>
                <td className="px-3 py-3"><SlaBadge sla={c.sla} /></td>
                <td className="whitespace-nowrap px-3 py-3 text-muted">{ago(c.queued_at)}</td>
                <td className="px-6 py-3">
                  <div className="flex flex-wrap gap-1">
                    {c.event_id !== null && (
                      <Badge tone="urgent" title="Arrivé pendant un événement climatique">
                        <CloudLightning size={11} aria-hidden /> événement
                      </Badge>
                    )}
                    <AnalysisBadge status={c.analysis_status} />
                    <HolderBadge holder={c.holder} me={me} />
                    {c.needs_check && (
                      <Badge tone="high" title="Confiance faible ou repli sur les règles">
                        <AlertTriangle size={11} aria-hidden /> à vérifier
                      </Badge>
                    )}
                    {c.status === "manuel" && <Badge>manuel</Badge>}
                  </div>
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-muted">{tab === "open" ? "Rien à traiter avec ce filtre." : "Aucun dossier traité."}</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
