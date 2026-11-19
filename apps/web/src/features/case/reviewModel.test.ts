import type { Suggestion } from "@/api/client";
import { blocker, initReview, reviewReducer, tally, toPayload } from "./reviewModel";

const FIELDS = ["numero_contrat", "date_sinistre", "fuite_active", "echeance"];

const suggestion = {
  category: "declaration_sinistre",
  confidence: 0.92,
  fields: { numero_contrat: "CT12345678", date_sinistre: "2026-11-17", fuite_active: true, echeance: null },
} as unknown as Suggestion;

describe("review model — AI mode", () => {
  it("starts with every suggested value accepted", () => {
    const s = initReview(FIELDS, suggestion);
    expect(s.mode).toBe("ai");
    expect(tally(s)).toEqual({ accepted: 4, edited: 0, rejected: 0 });
    expect(blocker(s)).toBeNull();
  });

  it("marks a changed value as edited, and back to accepted when restored", () => {
    let s = initReview(FIELDS, suggestion);
    s = reviewReducer(s, { type: "setField", name: "date_sinistre", value: "2026-11-16" });
    expect(s.fields.date_sinistre!.verdict).toBe("edited");
    s = reviewReducer(s, { type: "setField", name: "date_sinistre", value: "2026-11-17" });
    expect(s.fields.date_sinistre!.verdict).toBe("accepted");
  });

  it("a rejection clears the value and requires a reason", () => {
    let s = initReview(FIELDS, suggestion);
    s = reviewReducer(s, { type: "rejectField", name: "fuite_active" });
    expect(s.fields.fuite_active).toEqual({ value: null, verdict: "rejected" });
    expect(blocker(s)).toBe("Indiquez le motif du rejet");
    s = reviewReducer(s, { type: "setReason", code: "valeur_inventee" });
    expect(blocker(s)).toBeNull();
    expect(toPayload(s, 12.34, false).reason_code).toBe("valeur_inventee");
  });

  it("a new category counts as a correction", () => {
    const s = reviewReducer(initReview(FIELDS, suggestion), { type: "setCategory", value: "relance_delai" });
    expect(s.category).toEqual({ value: "relance_delai", verdict: "edited" });
  });

  it("the payload skips fields nobody suggested or touched", () => {
    const p = toPayload(initReview(FIELDS, suggestion), 30, false);
    expect(Object.keys(p.fields ?? {})).toEqual(["numero_contrat", "date_sinistre", "fuite_active"]);
    expect(p.seconds_to_decision).toBe(30);
    expect(p.reason_code).toBeNull();
  });

  it("a value added by the handler where the AI found nothing is an edit", () => {
    const s = reviewReducer(initReview(FIELDS, suggestion), {
      type: "setField",
      name: "echeance",
      value: "2026-11-25",
    });
    expect(toPayload(s, 1, false).fields?.echeance).toEqual({ verdict: "edited", value: "2026-11-25" });
  });
});

describe("review model — manual mode (control arm)", () => {
  it("records only what the handler typed, as manual entries", () => {
    let s = initReview(FIELDS, null);
    expect(s.mode).toBe("manual");
    expect(blocker(s)).toBe("Choisissez une catégorie");
    s = reviewReducer(s, { type: "setCategory", value: "reclamation" });
    s = reviewReducer(s, { type: "setField", name: "numero_contrat", value: "CT1" });
    const p = toPayload(s, 61, true);
    expect(p.category).toEqual({ verdict: "manual_entry", value: "reclamation" });
    expect(p.fields).toEqual({ numero_contrat: { verdict: "manual_entry", value: "CT1" } });
    expect(p.manual).toBe(true);
  });
});

describe("review model — confidence as behaviour", () => {
  it("asks for an explicit confirmation when the AI is unsure of the category", () => {
    const unsure = { ...suggestion, confidence: 0.6 } as unknown as Suggestion;
    let s = initReview(FIELDS, unsure);
    expect(blocker(s)).toMatch(/Confirmez la catégorie/);
    s = reviewReducer(s, { type: "confirmCategory" });
    expect(blocker(s)).toBeNull();
    expect(s.category.verdict).toBe("accepted");
  });

  it("choosing another category also counts as a confirmation", () => {
    const unsure = { ...suggestion, confidence: 0.5 } as unknown as Suggestion;
    const s = reviewReducer(initReview(FIELDS, unsure), { type: "setCategory", value: "relance_delai" });
    expect(blocker(s)).toBeNull();
  });
});
