import { formatValue, segmentText, snapToWords, toCsv } from "./utils";

describe("segmentText", () => {
  const text = "Contrat CT12345678, fuite active.";

  it("returns the whole text when there are no spans", () => {
    expect(segmentText(text, [])).toEqual([{ text }]);
  });

  it("highlights spans and keeps the text intact", () => {
    const segs = segmentText(text, [{ field: "numero_contrat", start: 8, end: 18 }]);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs[1]).toEqual({ text: "CT12345678", field: "numero_contrat" });
  });

  it("drops overlapping, out-of-range and unlocated spans", () => {
    const segs = segmentText(text, [
      { field: "a", start: 8, end: 18 },
      { field: "b", start: 10, end: 14 },
      { field: "c", start: null, end: null },
      { field: "d", start: 5, end: 999 },
    ]);
    expect(segs.filter((s) => s.field).map((s) => s.field)).toEqual(["a"]);
  });
});

describe("snapToWords", () => {
  const text = "Il s'agit de mon véhicule le immatriculé KZ-821-GZ, assuré sous le contrat.";

  it("trims cut words at both edges and keeps the value", () => {
    const start = text.indexOf("ule le");
    const end = text.indexOf("sous l") + "sous l".length;
    const [a, b] = snapToWords(text, start, end);
    expect(text.slice(a, b)).toBe("le immatriculé KZ-821-GZ, assuré sous");
  });

  it("leaves exact quotes untouched", () => {
    const start = text.indexOf("KZ-821-GZ");
    expect(snapToWords(text, start, start + 9)).toEqual([start, start + 9]);
  });
});

describe("formatting", () => {
  it("formats booleans and empty values in French", () => {
    expect(formatValue(true)).toBe("Oui");
    expect(formatValue(false)).toBe("Non");
    expect(formatValue(null)).toBe("—");
  });

  it("escapes CSV cells with separators", () => {
    const csv = toCsv([{ a: "x;y", b: ["r1", "r2"] }]);
    expect(csv.split("\n")[1]).toBe('"x;y";r1 | r2');
  });
});
