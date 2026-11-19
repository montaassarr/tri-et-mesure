import { AlertTriangle, Check, Hand, Quote, RotateCcw, X } from "lucide-react";
import { useState, type Dispatch } from "react";
import type { Meta, Suggestion } from "@/api/client";
import { confidenceLabel } from "@/components/status";
import { toast } from "@/components/toast";
import { Badge, Button, Card, inputClass, selectClass } from "@/components/ui";
import { cn, formatValue } from "@/lib/utils";
import { locateEvidence, SectionTitle } from "./parts";
import {
  blocker,
  isRelevant,
  needsReason,
  type FieldValue,
  type ReviewAction,
  type ReviewState,
} from "./reviewModel";

const BOOL_FIELDS = new Set(["besoin_relogement", "fuite_active", "personne_vulnerable"]);
const DATE_FIELDS = new Set(["date_sinistre", "echeance"]);

/** Column 2: the AI's proposal as an editable form, and the decision. */
export function DecisionPanel({
  state,
  dispatch,
  suggestion,
  meta,
  editable,
  busy,
  colorOf,
  onSubmit,
}: {
  state: ReviewState;
  dispatch: Dispatch<ReviewAction>;
  suggestion: Suggestion | null;
  meta: Meta;
  editable: boolean;
  busy: boolean;
  colorOf: (field: string) => string;
  onSubmit: (manual: boolean) => void;
}) {
  const ai = state.mode === "ai";
  const why = blocker(state);
  const conf = suggestion ? confidenceLabel(suggestion.confidence) : null;
  const located = new Set((suggestion?.spans ?? []).filter((s) => s.start !== null).map((s) => s.field));

  return (
    <Card className="flex flex-col">
      <SectionTitle help={ai ? "Proposition de l'IA" : undefined}
                    right={conf && <Badge tone={conf.tone}>{conf.label}</Badge>}>
        {ai ? "Proposition de l'IA" : "Saisie"}
      </SectionTitle>

      <div className="space-y-6 px-6 py-5">
        {ai && suggestion && <p className="rounded-2xl bg-p-sky px-4 py-3 text-[15px] leading-relaxed">{suggestion.summary}</p>}

        <div>
          <label htmlFor="field-category" className="text-sm font-semibold">Catégorie</label>
          <div className="mt-1.5 flex gap-2">
            <select id="field-category" className={cn(selectClass, "w-full", !state.categoryConfirmed && "border-high ring-2 ring-high/20")}
                    value={state.category.value as string} disabled={!editable}
                    onChange={(e) => dispatch({ type: "setCategory", value: e.target.value })}>
              <option value="">Choisir…</option>
              {Object.entries(meta.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            {editable && !state.categoryConfirmed && (
              <Button variant="secondary" onClick={() => dispatch({ type: "confirmCategory" })} title="L'IA n'est pas sûre de la catégorie">
                <Check size={15} aria-hidden /> Confirmer
              </Button>
            )}
          </div>
          {ai && state.category.verdict === "edited" && state.suggestedCategory && (
            <div className="mt-1 text-sm text-muted">IA : {meta.categories[state.suggestedCategory]}</div>
          )}
        </div>

        {meta.field_groups.map((group) => (
          <FieldGroup key={group.label} label={group.label} names={group.fields} state={state} dispatch={dispatch}
                      meta={meta} editable={editable} colorOf={colorOf} located={located} />
        ))}

        {editable && needsReason(state) && (
          <div>
            <label htmlFor="reject-reason" className="text-sm font-semibold text-urgent">Motif du rejet</label>
            <select id="reject-reason" className={cn(selectClass, "mt-1.5 w-full")} value={state.reasonCode}
                    onChange={(e) => dispatch({ type: "setReason", code: e.target.value })}>
              <option value="">Choisir…</option>
              {Object.entries(meta.reason_codes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
      </div>

      {editable && (
        <div className="sticky -bottom-8 z-10 rounded-b-3xl border-t border-line bg-white px-6 py-4 shadow-[0_-10px_20px_-16px_rgba(13,14,51,0.35)]">
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" onClick={() => onSubmit(false)} disabled={busy || why !== null} title="Ctrl + Entrée">
              <Check size={18} aria-hidden /> Valider
            </Button>
            <Button size="lg" variant="ghost" onClick={() => onSubmit(true)} disabled={busy || why !== null}
                    title="Le dossier sort du flux et sera traité à la main">
              <Hand size={16} aria-hidden /> Traiter à la main
            </Button>
          </div>
          {why && <div className="mt-2 text-sm text-high">{why}</div>}
        </div>
      )}
    </Card>
  );
}

function FieldGroup(props: {
  label: string;
  names: string[];
  state: ReviewState;
  dispatch: Dispatch<ReviewAction>;
  meta: Meta;
  editable: boolean;
  colorOf: (f: string) => string;
  located: Set<string>;
}) {
  const { names, state } = props;
  const [showAll, setShowAll] = useState(state.mode === "manual");
  const relevant = names.filter((n) => isRelevant(state, n));
  const visible = showAll ? names : relevant;
  const hidden = names.length - relevant.length;
  if (visible.length === 0 && !props.editable) return null;
  return (
    <fieldset>
      <legend className="mb-2.5 text-sm font-semibold">{props.label}</legend>
      <div className="space-y-3">
        {visible.map((name) => <FieldRow key={name} name={name} {...props} />)}
      </div>
      {!showAll && hidden > 0 && props.editable && (
        <button type="button" className="mt-2 text-sm font-semibold text-accent hover:underline" onClick={() => setShowAll(true)}>
          + Ajouter
        </button>
      )}
    </fieldset>
  );
}

function FieldRow({ name, state, dispatch, meta, editable, colorOf, located }: {
  name: string;
  state: ReviewState;
  dispatch: Dispatch<ReviewAction>;
  meta: Meta;
  editable: boolean;
  colorOf: (f: string) => string;
  located: Set<string>;
}) {
  const d = state.fields[name]!;
  const suggested = state.suggestedFields[name];
  const id = `field-${name}`;
  const label = meta.fields[name] ?? name;
  const set = (value: FieldValue) => dispatch({ type: "setField", name, value });
  const ai = state.mode === "ai";
  const proposed = ai && suggested !== null;
  const hasSource = located.has(name);
  const unsourced = proposed && !hasSource && d.verdict === "accepted";

  let input;
  if (BOOL_FIELDS.has(name)) {
    input = (
      <select id={id} className={cn(selectClass, "w-full")} disabled={!editable}
              value={d.value === null ? "" : String(d.value)}
              onChange={(e) => set(e.target.value === "" ? null : e.target.value === "true")}>
        <option value="">—</option><option value="true">Oui</option><option value="false">Non</option>
      </select>
    );
  } else if (name === "type_dommage") {
    input = (
      <select id={id} className={cn(selectClass, "w-full")} disabled={!editable}
              value={(d.value as string | null) ?? ""} onChange={(e) => set(e.target.value || null)}>
        <option value="">—</option>
        {Object.entries(meta.damages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
    );
  } else {
    input = (
      <input id={id} className={cn(inputClass, unsourced && "border-high")} disabled={!editable}
             type={DATE_FIELDS.has(name) ? "date" : "text"}
             value={(d.value as string | null) ?? ""} onChange={(e) => set(e.target.value || null)} />
    );
  }

  return (
    <div className="grid grid-cols-[9rem_1fr_auto] items-center gap-x-3">
      <label htmlFor={id} className="flex items-center gap-2 text-sm text-ink/80">
        <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full", hasSource ? colorOf(name) : "bg-transparent")} aria-hidden />
        <span className="truncate">{label}</span>
        {unsourced && <AlertTriangle size={14} className="shrink-0 text-high" aria-label="sans source dans l'e-mail" />}
      </label>
      {input}
      <div className="flex items-center">
        {proposed && hasSource && (
          <Button variant="ghost" size="sm" aria-label={`Voir ${label} dans l'e-mail`} title="Voir dans l'e-mail"
                  onClick={() => locateEvidence(name) || toast("Passage introuvable dans l'e-mail", "error")}>
            <Quote size={14} aria-hidden />
          </Button>
        )}
        {proposed && editable && d.verdict !== "rejected" && (
          <Button variant="ghost" size="sm" aria-label={`Rejeter ${label}`} title="Rejeter (valeur fausse ou inventée)"
                  onClick={() => dispatch({ type: "rejectField", name })}>
            <X size={14} aria-hidden />
          </Button>
        )}
        {ai && editable && d.verdict !== "accepted" && (
          <Button variant="ghost" size="sm" aria-label={`Rétablir ${label}`} title="Revenir à la proposition"
                  onClick={() => dispatch({ type: "resetField", name })}>
            <RotateCcw size={14} aria-hidden />
          </Button>
        )}
      </div>
      {(d.verdict === "edited" || d.verdict === "rejected") && suggested !== null && (
        <div className={cn("col-start-2 col-end-4 mt-1 text-sm", d.verdict === "rejected" ? "text-urgent" : "text-muted")}>
          {d.verdict === "rejected" ? "Rejeté" : "Corrigé"} · IA : {formatValue(suggested)}
        </div>
      )}
    </div>
  );
}
