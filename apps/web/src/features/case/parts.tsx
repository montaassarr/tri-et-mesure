/** Small building blocks of the case screen. */
import type { ReactNode } from "react";
import { InfoTip } from "@/components/InfoTip";

/** Section title; its explanation is behind (i), not printed under it. */
export function SectionTitle({ children, help, right }: { children: ReactNode; help?: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
      <h2 className="flex items-center gap-1.5 text-base font-bold">
        {children}
        {help && <InfoTip screen="case" name={help} />}
      </h2>
      {right}
    </div>
  );
}

/** Scroll to and flash the evidence of a field in the e-mail. */
export function locateEvidence(field: string) {
  const el = document.getElementById(`ev-${field}`);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("ring-2", "ring-accent", "ring-offset-1");
  setTimeout(() => el.classList.remove("ring-2", "ring-accent", "ring-offset-1"), 1600);
  return true;
}
