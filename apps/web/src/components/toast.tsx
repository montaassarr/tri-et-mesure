import { CheckCircle2, XCircle } from "lucide-react";
import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

interface Toast {
  id: number;
  tone: "ok" | "error";
  text: string;
}

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

/** Short confirmation after an action ("Dossier validé"). Disappears after 3.5 s. */
export function toast(text: string, tone: Toast["tone"] = "ok") {
  const id = nextId++;
  toasts = [...toasts, { id, tone, text }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, 3500);
}

export function Toaster() {
  const items = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => toasts,
  );
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
      {items.map((t) => (
        <div
          key={t.id}
          className={cn(
            "flex items-center gap-2 rounded-lg border bg-white px-4 py-2.5 text-sm shadow-lg",
            t.tone === "ok" ? "border-ok/30 text-ok" : "border-urgent/30 text-urgent",
          )}
        >
          {t.tone === "ok" ? <CheckCircle2 size={16} aria-hidden /> : <XCircle size={16} aria-hidden />}
          <span className="text-ink">{t.text}</span>
        </div>
      ))}
    </div>
  );
}
