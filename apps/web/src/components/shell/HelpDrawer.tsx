import { Keyboard, Lightbulb, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { SCREENS, screenKey } from "@/help/content";
import { cn } from "@/lib/utils";

/** "?" drawer: what this screen is for, when to use it, how, and why each element exists. */
export function HelpDrawer({ open, onClose, path }: { open: boolean; onClose: () => void; path: string; role: string }) {
  const help = SCREENS[screenKey(path)]!;
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) panel.current?.focus();
  }, [open]);

  return (
    <div className={cn("fixed inset-0 z-40 print:hidden", open ? "" : "pointer-events-none")} aria-hidden={!open}>
      <div className={cn("absolute inset-0 bg-ink/20 transition-opacity", open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <aside
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Aide : ${help.title}`}
        className={cn(
          "absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-white shadow-2xl outline-none transition-transform",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-6 py-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-accent">Comment ça marche</div>
            <h2 className="mt-1 text-xl font-bold">{help.title}</h2>
            <p className="mt-1 text-sm text-muted">{help.purpose}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-surface" aria-label="Fermer l'aide">
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5 text-sm">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Quand l'utiliser</h3>
            <p className="mt-1.5">{help.when}</p>
          </section>
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Comment</h3>
            <ol className="mt-2 space-y-2">
              {help.steps.map((s, i) => (
                <li key={s} className="flex gap-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-xs font-bold text-white">{i + 1}</span>
                  <span className="pt-0.5">{s}</span>
                </li>
              ))}
            </ol>
          </section>
          {help.elements.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Chaque élément, et pourquoi il existe</h3>
              <dl className="mt-2 space-y-3">
                {help.elements.map((e) => (
                  <div key={e.name} className="rounded-2xl bg-surface p-3.5">
                    <dt className="font-semibold">{e.name}</dt>
                    <dd className="mt-1 text-ink/90">{e.what}</dd>
                    <dd className="mt-1.5 flex gap-1.5 text-xs text-muted">
                      <Lightbulb size={13} className="mt-0.5 shrink-0 text-high" aria-hidden /> {e.why}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          {help.shortcuts && (
            <section>
              <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
                <Keyboard size={13} aria-hidden /> Raccourcis
              </h3>
              <ul className="mt-2 space-y-1.5">
                {help.shortcuts.map(([k, v]) => (
                  <li key={k} className="flex items-center justify-between">
                    <span>{v}</span>
                    <kbd className="rounded-md border border-line bg-surface px-2 py-0.5 font-mono text-xs">{k}</kbd>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
