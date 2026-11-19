import { ShieldCheck } from "lucide-react";
import type { CaseDetail, Meta } from "@/api/client";
import { Badge, Card, Disclosure, Notice } from "@/components/ui";
import { cn, formatEur, segmentText } from "@/lib/utils";
import { SectionTitle } from "./parts";

/** Column 1: what the customer wrote, with the evidence behind each AI value. */
export function EmailPanel({ detail, meta, colorOf }: { detail: CaseDetail; meta: Meta; colorOf: (f: string) => string }) {
  const s = detail.suggestion;
  const lastCall = detail.llm_calls.at(-1);
  const seen = new Set<string>();
  const maskedTotal = Object.values(detail.pii_counts).reduce((a, b) => a + b, 0);

  return (
    <Card className="self-start overflow-hidden">
      <SectionTitle help="Passages surlignés">E-mail</SectionTitle>
      <div className="px-6 py-4">
        <div className="mb-3 text-sm text-muted">{detail.sender_email}</div>
        {detail.body === null ? (
          <Notice tone="neutral">Texte original effacé (durée de conservation dépassée). Seule la version masquée est conservée.</Notice>
        ) : (
          <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
            {segmentText(detail.body, s?.spans ?? []).map((seg, i) => {
              if (!seg.field) return <span key={i}>{seg.text}</span>;
              const first = !seen.has(seg.field);
              seen.add(seg.field);
              return (
                <mark key={i} id={first ? `ev-${seg.field}` : undefined}
                      className={cn("transition-shadow", colorOf(seg.field))} title={meta.fields[seg.field] ?? seg.field}>
                  {seg.text}
                </mark>
              );
            })}
          </div>
        )}
      </div>

      {s && (
        <Disclosure
          title={
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck size={15} className="text-ok" aria-hidden />
              Détails techniques · {maskedTotal} données masquées
            </span>
          }
        >
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
            <Meta label="Source" value={s.source === "interne" ? "Pipeline interne" : `IA externe · ${s.source}`} />
            <Meta label="Modèle" value={s.model} />
            <Meta label="Version du prompt" value={s.prompt_version} />
            {lastCall && <Meta label="Jetons" value={`${lastCall.input_tokens} → ${lastCall.output_tokens}`} />}
            <Meta label="Coût" value={formatEur(s.cost_eur, 6)} />
            <Meta label="Latence" value={lastCall ? `${lastCall.latency_ms} ms` : s.latency_ms !== null ? `${s.latency_ms} ms` : "—"} />
          </dl>
          {s.used_fallback && <div className="mt-2"><Badge tone="high">Règles de secours</Badge></div>}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {Object.entries(detail.pii_counts).map(([kind, n]) => <Badge key={kind} tone="ok">{kind} ×{n}</Badge>)}
          </div>
          <div className="mt-4 text-sm font-semibold">Texte envoyé à l'IA</div>
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded-2xl bg-surface p-3 text-xs">
            {lastCall?.masked_prompt?.split("=== USER ===")[1]?.trim() ?? `Objet : ${detail.subject_masked}\n${detail.body_masked}`}
          </pre>
        </Disclosure>
      )}
    </Card>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}
