import { CloudHail, CloudLightning, Waves } from "lucide-react";
import { useState } from "react";
import { useCrisis, useEndCrisis, useStartCrisis } from "@/api/hooks";
import { useCan } from "@/auth/session";
import { toast } from "@/components/toast";
import { Button, Card, CardHeader, ErrorNotice, HighlightCard, inputClass, Kpi, selectClass } from "@/components/ui";
import { ago } from "@/lib/time";
import { cn } from "@/lib/utils";

type Kind = "grele" | "tempete" | "inondation";
const KINDS: Record<Kind, { label: string; icon: typeof CloudHail; name: string }> = {
  grele: { label: "Grêle", icon: CloudHail, name: "Orage de grêle — Toulouse" },
  tempete: { label: "Tempête", icon: CloudLightning, name: "Tempête — façade atlantique" },
  inondation: { label: "Inondation", icon: Waves, name: "Crue — vallée du Rhône" },
};

/** Storm mode: declare a climate event, then follow the surge live. */
export function CrisisCard() {
  const crisis = useCrisis();
  const start = useStartCrisis();
  const end = useEndCrisis();
  const canManage = useCan("crisis.manage");
  const [kind, setKind] = useState<Kind>("grele");
  const [name, setName] = useState(KINDS.grele.name);
  const [volume, setVolume] = useState(150);

  const c = crisis.data;
  if (c) {
    const Icon = KINDS[c.kind as Kind]?.icon ?? CloudLightning;
    return (
      <Card className="border-urgent/30 ring-1 ring-urgent/10">
        <CardHeader
          title={<span className="inline-flex items-center gap-2 text-urgent"><Icon size={17} aria-hidden /> Événement en cours : {c.name}</span>}
          hint={`${c.kind_label} déclarée ${ago(c.started_at)} · le flux suit le chemin normal (masquage, IA, règles, décision humaine)`}
        >
          {canManage && (
            <Button variant="secondary" size="sm" disabled={end.isPending}
                    onClick={() => end.mutate(c.id, { onSuccess: () => toast("Événement clôturé") })}>
              Clôturer l'événement
            </Button>
          )}
        </CardHeader>
        <div className="grid gap-3 px-5 py-4 sm:grid-cols-2 lg:grid-cols-5">
          <Kpi label="E-mails reçus" value={c.received} hint={c.waiting_analysis ? `${c.waiting_analysis} en analyse IA` : "tous analysés"} />
          <Kpi label="À traiter" value={c.open} hint={`dont ${c.urgent_open} urgent(s)`} tone={c.urgent_open ? "high" : undefined} />
          <Kpi label="En retard" value={c.late} tone={c.late ? "urgent" : undefined} />
          <Kpi label="Traités (dernière heure)" value={c.closed_last_hour} hint={`${c.closed} au total`} />
          <Kpi label="Résorption estimée" value={c.hours_to_clear !== null ? `${c.hours_to_clear} h` : "—"}
               hint={c.hours_to_clear !== null ? "au rythme de la dernière heure" : "traitez quelques dossiers pour l'estimer"} />
        </div>
        <div className="border-t border-line px-5 py-3 text-sm text-muted">
          Temps médian par dossier pendant l'événement : avec IA{" "}
          <strong className="text-ink">{c.median_seconds.ai !== null ? `${c.median_seconds.ai} s` : "—"}</strong> · sans IA{" "}
          <strong className="text-ink">{c.median_seconds.control !== null ? `${c.median_seconds.control} s` : "—"}</strong>
        </div>
      </Card>
    );
  }

  if (!canManage) return null;
  return (
    <HighlightCard title="Mode tempête">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          start.mutate({ name, kind, volume }, { onSuccess: (r) => toast(`${r.received} e-mails reçus : « ${r.name} »`) });
        }}
      >
        <label className="text-xs text-white/70">
          Événement
          <select className={cn(selectClass, "mt-1 block text-ink")} value={kind}
                  onChange={(e) => { const k = e.target.value as Kind; setKind(k); setName(KINDS[k].name); }}>
            {(Object.keys(KINDS) as Kind[]).map((k) => <option key={k} value={k}>{KINDS[k].label}</option>)}
          </select>
        </label>
        <label className="min-w-56 flex-1 text-xs text-white/70">
          Nom
          <input className={cn(inputClass, "mt-1 text-ink")} value={name} minLength={3} maxLength={120}
                 onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="text-xs text-white/70">
          Volume
          <select className={cn(selectClass, "mt-1 block text-ink")} value={volume} onChange={(e) => setVolume(Number(e.target.value))}>
            {[50, 100, 150, 300].map((v) => <option key={v} value={v}>{v} e-mails</option>)}
          </select>
        </label>
        <Button type="submit" variant="light" disabled={start.isPending}>
          <CloudLightning size={15} aria-hidden /> {start.isPending ? "Arrivée des e-mails…" : "Déclencher"}
        </Button>
      </form>
      {start.error && <div className="mt-3"><ErrorNotice error={start.error} /></div>}
    </HighlightCard>
  );
}
