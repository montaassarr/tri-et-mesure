/** Human-readable French durations: "il y a 2 h", "dans 35 min", "1 h 20 de retard". */

export function formatDuration(minutes: number): string {
  const m = Math.abs(Math.round(minutes));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h < 24) return rest ? `${h} h ${String(rest).padStart(2, "0")}` : `${h} h`;
  const d = Math.floor(h / 24);
  return `${d} j ${h % 24} h`;
}

export function ago(iso: string, now: Date = new Date()): string {
  const minutes = (now.getTime() - new Date(iso).getTime()) / 60_000;
  if (minutes < 1) return "à l'instant";
  return `il y a ${formatDuration(minutes)}`;
}

/** Wording for a service-level clock. */
export function slaText(minutesLeft: number, state: string): string {
  if (state === "termine") return "traité";
  if (minutesLeft < 0) return `${formatDuration(minutesLeft)} de retard`;
  return `reste ${formatDuration(minutesLeft)}`;
}
