/**
 * The review form as a pure state machine (no React): easy to test, easy to explain.
 *
 * AI mode      — values start from the suggestion. Untouched = accepted; changed = edited;
 *                ✕ = rejected (the value was wrong or invented; a reason is required).
 * Manual mode  — control arm: nothing is suggested, every value is a manual entry.
 *
 * Confidence is shown as behaviour, not as a percentage: when the AI is not sure of the
 * category (confidence < CONFIRM_BELOW), the handler must confirm it explicitly before
 * validating. This prevents rubber-stamping exactly where the AI is weakest.
 */
import type { ReviewIn, Suggestion } from "@/api/client";

export const CONFIRM_BELOW = 0.85;

export type Verdict = "accepted" | "edited" | "rejected" | "manual_entry";
export type FieldValue = string | boolean | null;

export interface Decision {
  verdict: Verdict;
  value: FieldValue;
}

export interface ReviewState {
  mode: "ai" | "manual";
  suggestedCategory: string | null;
  suggestedFields: Record<string, FieldValue>;
  category: Decision;
  categoryConfirmed: boolean;
  fields: Record<string, Decision>;
  reasonCode: string;
}

export type ReviewAction =
  | { type: "setCategory"; value: string }
  | { type: "confirmCategory" }
  | { type: "setField"; name: string; value: FieldValue }
  | { type: "rejectField"; name: string }
  | { type: "resetField"; name: string }
  | { type: "setReason"; code: string };

const same = (a: FieldValue | undefined, b: FieldValue | undefined) => (a ?? null) === (b ?? null);

export function initReview(fieldNames: string[], suggestion: Suggestion | null): ReviewState {
  const mode = suggestion ? "ai" : "manual";
  const suggestedFields: Record<string, FieldValue> = {};
  const fields: Record<string, Decision> = {};
  for (const name of fieldNames) {
    const v = (suggestion?.fields[name] ?? null) as FieldValue;
    suggestedFields[name] = v;
    fields[name] = { verdict: mode === "ai" ? "accepted" : "manual_entry", value: v };
  }
  return {
    mode,
    suggestedCategory: suggestion?.category ?? null,
    suggestedFields,
    category: {
      verdict: mode === "ai" ? "accepted" : "manual_entry",
      value: suggestion?.category ?? "",
    },
    categoryConfirmed: mode === "manual" || (suggestion?.confidence ?? 0) >= CONFIRM_BELOW,
    fields,
    reasonCode: "",
  };
}

export function reviewReducer(state: ReviewState, action: ReviewAction): ReviewState {
  switch (action.type) {
    case "confirmCategory":
      return { ...state, categoryConfirmed: true };
    case "setCategory":
      return {
        ...state,
        categoryConfirmed: true,
        category: {
          value: action.value,
          verdict:
            state.mode === "manual"
              ? "manual_entry"
              : action.value === state.suggestedCategory
                ? "accepted"
                : "edited",
        },
      };
    case "setField": {
      const suggested = state.suggestedFields[action.name];
      const verdict: Verdict =
        state.mode === "manual" ? "manual_entry" : same(action.value, suggested) ? "accepted" : "edited";
      return { ...state, fields: { ...state.fields, [action.name]: { value: action.value, verdict } } };
    }
    case "rejectField":
      return {
        ...state,
        fields: { ...state.fields, [action.name]: { value: null, verdict: "rejected" } },
      };
    case "resetField":
      return {
        ...state,
        fields: {
          ...state.fields,
          [action.name]: {
            value: state.suggestedFields[action.name] ?? null,
            verdict: state.mode === "ai" ? "accepted" : "manual_entry",
          },
        },
      };
    case "setReason":
      return { ...state, reasonCode: action.code };
  }
}

/** Fields worth showing by default: suggested, or touched by the handler. */
export function isRelevant(state: ReviewState, name: string): boolean {
  const d = state.fields[name];
  return state.suggestedFields[name] !== null || (d !== undefined && (d.value !== null || d.verdict === "rejected"));
}

export function needsReason(state: ReviewState): boolean {
  return Object.values(state.fields).some((d) => d.verdict === "rejected");
}

export function blocker(state: ReviewState): string | null {
  if (!state.category.value) return "Choisissez une catégorie";
  if (!state.categoryConfirmed) return "Confirmez la catégorie proposée (l'IA n'en est pas sûre)";
  if (needsReason(state) && !state.reasonCode) return "Indiquez le motif du rejet";
  return null;
}

export function tally(state: ReviewState) {
  const all = [state.category, ...Object.entries(state.fields)
    .filter(([name]) => isRelevant(state, name))
    .map(([, d]) => d)];
  return {
    accepted: all.filter((d) => d.verdict === "accepted").length,
    edited: all.filter((d) => d.verdict === "edited").length,
    rejected: all.filter((d) => d.verdict === "rejected").length,
  };
}

export function toPayload(state: ReviewState, seconds: number, manual: boolean): ReviewIn {
  const fields: ReviewIn["fields"] = {};
  for (const [name, d] of Object.entries(state.fields)) {
    // Nothing suggested and nothing entered: there was no decision to record.
    if (state.mode === "manual" ? d.value === null : !isRelevant(state, name)) continue;
    fields[name] = { verdict: d.verdict, value: d.value };
  }
  return {
    category: { verdict: state.category.verdict, value: state.category.value },
    fields,
    reason_code: needsReason(state) ? state.reasonCode : null,
    manual,
    seconds_to_decision: Math.min(Math.round(seconds * 10) / 10, 3600),
  };
}
