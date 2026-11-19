import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const dateFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

export function formatEur(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "—";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: digits })} €`;
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (value === true) return "Oui";
  if (value === false) return "Non";
  return String(value);
}

export interface Segment {
  text: string;
  field?: string;
}

const WORD = /[\p{L}\p{N}]/u;

/**
 * Trim a span that starts or ends in the middle of a word ("su[r mon véhicule]") back to
 * whole words. Quotes cut by a fixed-size window are hard to read and look like a bug;
 * the value itself sits in the middle of the quote, so trimming the edges never loses it.
 */
export function snapToWords(text: string, start: number, end: number): [number, number] {
  let a = start;
  let b = end;
  if (a > 0 && WORD.test(text[a - 1]!) && WORD.test(text[a]!)) {
    while (a < b && WORD.test(text[a]!)) a++;
    while (a < b && /\s/.test(text[a]!)) a++;
  }
  if (b < text.length && WORD.test(text[b]!) && WORD.test(text[b - 1]!)) {
    while (b > a && WORD.test(text[b - 1]!)) b--;
    while (b > a && /\s/.test(text[b - 1]!)) b--;
  }
  return b > a ? [a, b] : [start, end];
}

/**
 * Split `text` into plain and highlighted segments from (possibly overlapping) spans.
 * Spans are trimmed to whole words; overlaps keep the earliest, then longest, span.
 */
export function segmentText(
  text: string,
  spans: { field: string; start: number | null; end: number | null }[],
): Segment[] {
  const valid = spans
    .filter((s): s is { field: string; start: number; end: number } =>
      s.start !== null && s.end !== null && s.start >= 0 && s.end <= text.length && s.end > s.start,
    )
    .map((s) => {
      const [start, end] = snapToWords(text, s.start, s.end);
      return { ...s, start, end };
    })
    .sort((a, b) => a.start - b.start || b.end - a.end);

  const segments: Segment[] = [];
  let cursor = 0;
  for (const span of valid) {
    if (span.start < cursor) continue;
    if (span.start > cursor) segments.push({ text: text.slice(cursor, span.start) });
    segments.push({ text: text.slice(span.start, span.end), field: span.field });
    cursor = span.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments;
}

export function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]!);
  const escape = (v: unknown) => {
    const s = Array.isArray(v) ? v.join(" | ") : formatValue(v);
    return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [headers.join(";"), ...rows.map((r) => headers.map((h) => escape(r[h])).join(";"))].join(
    "\n",
  );
}

export function download(filename: string, content: string, type = "text/csv;charset=utf-8") {
  const blob = new Blob(["﻿", content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const FIELD_COLORS = [
  "bg-sky-100",
  "bg-amber-100",
  "bg-emerald-100",
  "bg-violet-100",
  "bg-rose-100",
  "bg-lime-100",
  "bg-orange-100",
  "bg-teal-100",
  "bg-fuchsia-100",
];
