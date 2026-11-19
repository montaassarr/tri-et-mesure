import { Link, useNavigate } from "@tanstack/react-router";
import { AlertTriangle, ArrowLeft, CheckCircle2, FlaskConical, Info, Loader2, Lock, Repeat2, Scale } from "lucide-react";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";
import type { CaseDetail, Meta } from "@/api/client";
import { useCase, useClaim, useMeta, useNextCase, useRelease, useReview } from "@/api/hooks";
import { useCan, useSession } from "@/auth/session";
import { InfoTip } from "@/components/InfoTip";
import { InTitleSlot } from "@/components/shell/TitleSlot";
import { CategoryTile, PriorityBadge, SlaBadge } from "@/components/status";
import { toast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, ErrorNotice, Notice, PageSkeleton, type Tone } from "@/components/ui";
import { FIELD_COLORS, formatDate, formatValue } from "@/lib/utils";
import { ContextPanel, useCaseContext } from "./ContextPanel";
import { DecisionPanel } from "./DecisionPanel";
import { EmailPanel } from "./EmailPanel";
import { blocker, initReview, reviewReducer, toPayload, type ReviewState } from "./reviewModel";

const LEASE_RENEW_MS = 5 * 60_000;

export function CasePage({ id }: { id: number }) {
  const detail = useCase(id);
  const meta = useMeta();
  if (detail.isLoading || meta.isLoading) return <PageSkeleton />;
  if (detail.error) return <ErrorNotice error={detail.error} />;
  if (meta.error) return <ErrorNotice error={meta.error} />;
  // Only the AI arm waits for the analysis; the control arm never sees it before closing.
  const analysing =
    detail.data!.arm === "ai" &&
    (detail.data!.analysis_status === "pending" || detail.data!.analysis_status === "running");
  // Remount the form once the suggestion arrives, so it starts from the AI's values.
  return (
    <Case
      key={`${id}-${detail.data!.suggestion?.id ?? "none"}-${analysing}`}
      detail={detail.data!}
      meta={meta.data!}
      analysing={analysing}
    />
  );
}

/** What deserves a second look before validating, in the handler's words. */
function verdictReasons(detail: CaseDetail, state: ReviewState, meta: Meta) {
  const s = detail.suggestion;
  if (!s || state.mode !== "ai") return null;
  const located = new Set(s.spans.filter((x) => x.start !== null).map((x) => x.field));
  const unsourced = Object.entries(state.suggestedFields)
    .filter(([name, v]) => v !== null && !located.has(name) && state.fields[name]?.verdict === "accepted")
    .map(([name]) => name);
  const out: { text: ReactNode; field?: string }[] = [];
  if (s.used_fallback) out.push({ text: "Proposition faite par les règles de secours (modèle indisponible)" });
  if (!state.categoryConfirmed) out.push({ text: "Catégorie à confirmer" });
  for (const name of unsourced) {
    out.push({ field: name, text: <>{meta.fields[name] ?? name} : sans source dans l'e-mail</> });
  }
  if (out.length === 0 && s.needs_manual && s.manual_reason) out.push({ text: s.manual_reason });
  return out;
}

function Case({ detail, meta, analysing }: { detail: CaseDetail; meta: Meta; analysing: boolean }) {
  const me = useSession()?.user.name;
  const canReview = useCan("cases.review");
  const claim = useClaim(detail.id);
  const release = useRelease(detail.id);
  const review = useReview(detail.id);
  const next = useNextCase();
  const navigate = useNavigate();

  const fieldNames = Object.keys(meta.fields);
  const [state, dispatch] = useReducer(reviewReducer, undefined, () =>
    initReview(fieldNames, detail.suggestion ?? null),
  );
  const startedAt = useRef(performance.now());
  const [claimError, setClaimError] = useState<unknown>(null);

  const isOpen = detail.status === "nouveau";
  const heldByOther = detail.holder !== null && detail.holder !== me;
  const mine = detail.holder === me;
  const editable = canReview && isOpen && mine && !analysing;
  const colorOf = useCallback(
    (f: string) => FIELD_COLORS[fieldNames.indexOf(f) % FIELD_COLORS.length] ?? "bg-sky-100",
    [fieldNames],
  );

  // Take the case on arrival and keep the lease alive while the page is open.
  const { mutate: doClaim } = claim;
  useEffect(() => {
    if (!canReview || !isOpen || heldByOther) return;
    const take = () => doClaim(undefined, { onError: setClaimError });
    if (!mine) take();
    const t = setInterval(take, LEASE_RENEW_MS);
    return () => clearInterval(t);
  }, [canReview, isOpen, heldByOther, mine, doClaim]);

  const submit = useCallback(
    async (manual: boolean) => {
      const seconds = (performance.now() - startedAt.current) / 1000;
      await review.mutateAsync(toPayload(state, seconds, manual));
      toast(manual ? "Dossier envoyé en traitement manuel" : "Dossier validé");
      const nextId = await next.mutateAsync();
      if (nextId) navigate({ to: "/dossier/$id", params: { id: String(nextId) } });
      else navigate({ to: "/" });
    },
    [review, state, next, navigate],
  );

  // Ctrl/Cmd + Enter validates (power users process dozens of cases in a row).
  useEffect(() => {
    if (!editable) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !review.isPending && blocker(state) === null) {
        e.preventDefault();
        submit(false).catch(() => undefined);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editable, submit, review.isPending, state]);

  const s = detail.suggestion;
  const reasons = isOpen && !analysing ? verdictReasons(detail, state, meta) : null;
  const category = (state.category.value as string) || s?.category || null;

  // A follow-up is handled differently from a new claim: say it before anything else.
  const ctx = useCaseContext(detail.id, state);
  const followUp = (ctx.related.data ?? []).length > 0;
  const frames = ctx.category ? ctx.playbook.data?.frames ?? [] : [];

  const notices = useMemo(() => {
    const out: { tone: Tone; icon: ReactNode; text: ReactNode }[] = [];
    if (analysing) out.push({ tone: "accent", icon: <Loader2 size={15} className="animate-spin" />, text: "Analyse en cours…" });
    if (detail.arm === "control" && isOpen) out.push({ tone: "neutral", icon: <FlaskConical size={15} />, text: <><strong>Groupe témoin</strong> : traitement sans IA.</> });
    if (heldByOther && isOpen) out.push({ tone: "neutral", icon: <Lock size={15} />, text: <>Ouvert par <strong>{detail.holder}</strong> · lecture seule</> });
    if (!canReview && isOpen) out.push({ tone: "neutral", icon: <Info size={15} />, text: "Lecture seule" });
    return out;
  }, [analysing, detail, isOpen, heldByOther, canReview]);

  return (
    <div className="space-y-4">
      <InTitleSlot>
        <h1 className="truncate text-[28px] font-extrabold tracking-tight">Dossier n° {detail.id}</h1>
      </InTitleSlot>

      <Card className="flex flex-wrap items-center gap-4 px-6 py-4">
        <Link to="/" aria-label="Retour à la corbeille" title="Corbeille"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink">
          <ArrowLeft size={18} aria-hidden />
        </Link>
        <CategoryTile category={category} size={48} />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-bold">{detail.subject}</h2>
          <div className="mt-0.5 text-sm text-muted">
            {category ? meta.categories[category] ?? category : "Catégorie à choisir"} · {formatDate(detail.received_at)}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {followUp && (
            <Badge tone="accent" title="Ce client a d'autres dossiers : voir l'onglet Historique">
              <Repeat2 size={12} aria-hidden /> Relance
            </Badge>
          )}
          {frames.map((fr) => (
            <Badge key={fr.name} title={[fr.summary, ...fr.deadlines].join(" · ")}>
              <Scale size={12} aria-hidden /> {fr.name.split(" (")[0]}
            </Badge>
          ))}
          <PriorityBadge priority={s?.priority ?? null} reasons={s?.priority_reasons} />
          <SlaBadge sla={detail.sla} />
          {mine && isOpen && (
            <Button variant="ghost" size="sm" disabled={release.isPending} title="Rendre le dossier à la corbeille"
                    onClick={() => release.mutate(undefined, { onSuccess: () => navigate({ to: "/" }) })}>
              Libérer
            </Button>
          )}
        </div>
      </Card>

      {reasons && <Verdict reasons={reasons} />}

      {notices.map((n, i) => (
        <Notice key={i} tone={n.tone} icon={n.icon}>
          {n.text}
        </Notice>
      ))}
      {claimError !== null && <ErrorNotice error={claimError} />}
      {review.error && <ErrorNotice error={review.error} />}

      <div className="grid items-start gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)_minmax(0,0.95fr)]">
        <EmailPanel detail={detail} meta={meta} colorOf={colorOf} />
        <div className="self-start">
          {isOpen ? (
            <DecisionPanel
              state={state}
              dispatch={dispatch}
              suggestion={s ?? null}
              meta={meta}
              editable={editable}
              busy={review.isPending || next.isPending}
              colorOf={colorOf}
              onSubmit={(manual) => submit(manual).catch(() => undefined)}
            />
          ) : (
            <ClosedCase detail={detail} meta={meta} />
          )}
        </div>
        <div className="lg:col-span-2 xl:col-span-1">
          <ContextPanel detail={detail} meta={meta} state={state} />
        </div>
      </div>
    </div>
  );
}

/** Silent when all is fine; when not, the few points to look at, each one clickable. */
function Verdict({ reasons }: { reasons: { text: ReactNode; field?: string }[] }) {
  if (reasons.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm font-semibold text-ok" role="status">
        <CheckCircle2 size={18} aria-hidden /> Prêt à valider
        <InfoTip screen="case" name="Verdict" />
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3 rounded-2xl bg-high-soft px-5 py-3.5" role="status">
      <AlertTriangle size={20} className="mt-0.5 shrink-0 text-high" aria-hidden />
      <div className="min-w-0">
        <div className="font-bold text-high">À vérifier</div>
        <ul className="mt-0.5 space-y-0.5 text-sm">
          {reasons.map((r, i) => (
            <li key={i}>
              {r.field ? (
                <button type="button" className="text-left underline-offset-2 hover:underline"
                        onClick={() => document.getElementById(`field-${r.field}`)?.focus()}>
                  {r.text}
                </button>
              ) : (
                r.text
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ClosedCase({ detail, meta }: { detail: CaseDetail; meta: Meta }) {
  const r = detail.reviews[0];
  if (!r) return null;
  const counts = Object.values(r.verdicts).reduce<Record<string, number>>((acc, v) => {
    acc[v] = (acc[v] ?? 0) + 1;
    return acc;
  }, {});
  const labels: Record<string, string> = {
    accepted: "accepté(s)", edited: "corrigé(s)", rejected: "rejeté(s)", manual_entry: "saisi(s)",
  };
  return (
    <Card>
      <CardHeader
        title={r.manual ? "Envoyé en traitement manuel" : "Dossier traité"}
        hint={`par ${r.reviewer} en ${Math.round(r.seconds_to_decision)} s`}
      />
      <div className="space-y-3 px-6 py-5 text-sm">
        <div>
          Catégorie retenue : <strong>{meta.categories[r.category] ?? r.category}</strong>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(counts).map(([k, n]) => (
            <Badge key={k}>
              {n} {labels[k] ?? k}
            </Badge>
          ))}
        </div>
        {Object.keys(r.diff).length > 0 && (
          <div>
            <div className="text-xs font-semibold text-muted">Corrections apportées à l'IA</div>
            <ul className="mt-1 space-y-0.5 text-xs">
              {Object.entries(r.diff).map(([k, d]) => {
                const diff = d as { from: unknown; to: unknown };
                const label = k === "category" ? "Catégorie" : meta.fields[k] ?? k;
                return (
                  <li key={k}>
                    {label} : <span className="text-muted line-through">{formatValue(diff.from)}</span> →{" "}
                    <strong>{formatValue(diff.to)}</strong>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
