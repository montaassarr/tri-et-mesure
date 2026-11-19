import { Link } from "@tanstack/react-router";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAlerts, useCases, useCrisis } from "@/api/hooks";
import { useCan } from "@/auth/session";
import { cn } from "@/lib/utils";

interface Item {
  key: string;
  text: string;
  tone: "urgent" | "high" | "neutral";
  to: string;
}

/** One bell, role-aware: what *you* should look at now. */
export function Notifications() {
  const canReview = useCan("cases.review");
  const canPilot = useCan("pilotage.read");
  const canAi = useCan("eval.read");
  const cases = useCases();
  const alerts = useAlerts(canAi);
  const crisis = useCrisis(canPilot);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const items: Item[] = [];
  const open_ = (cases.data ?? []).filter((c) => c.status === "nouveau");
  const late = open_.filter((c) => c.sla.state === "en_retard").length;
  const urgent = open_.filter((c) => c.priority === "urgente").length;
  if ((canReview || canPilot) && late) items.push({ key: "late", text: `${late} dossier(s) en retard sur leur délai cible`, tone: "urgent", to: "/" });
  if (canReview && urgent) items.push({ key: "urgent", text: `${urgent} dossier(s) urgent(s) à traiter en premier`, tone: "high", to: "/" });
  if (canPilot && crisis.data) items.push({ key: "crisis", text: `Événement en cours : ${crisis.data.name}`, tone: "urgent", to: "/pilotage" });
  if (canAi) for (const a of alerts.data ?? []) items.push({ key: a.code, text: a.title, tone: a.severity === "critique" ? "urgent" : "high", to: "/ia" });

  return (
    <div className="relative" ref={box}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
              aria-label={`Notifications (${items.length})`}
              className="relative grid h-10 w-10 place-items-center rounded-full bg-surface text-ink hover:bg-accent-soft hover:text-accent">
        <Bell size={19} aria-hidden />
        {items.length > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-brand-red px-1 text-xs font-bold text-white">
            {items.length}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 z-30 w-80 rounded-2xl border border-line bg-white p-2 shadow-soft">
          <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted">À regarder maintenant</div>
          {items.length === 0 ? (
            <p className="px-3 pb-3 text-sm text-muted">Rien d'urgent. Bon travail.</p>
          ) : (
            <ul>
              {items.map((it) => (
                <li key={it.key}>
                  <Link to={it.to} onClick={() => setOpen(false)}
                        className="flex items-start gap-2.5 rounded-xl px-3 py-2.5 text-sm hover:bg-surface">
                    <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full",
                      it.tone === "urgent" ? "bg-urgent" : it.tone === "high" ? "bg-high" : "bg-muted")} aria-hidden />
                    {it.text}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
