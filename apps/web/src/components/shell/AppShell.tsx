import { useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { BookOpen, BrainCircuit, CircleHelp, Gauge, Inbox, LogOut, ScrollText } from "lucide-react";
import { useEffect, useState } from "react";
import { session, useSession } from "@/auth/session";
import { cn } from "@/lib/utils";
import { Toaster } from "../toast";
import { HelpDrawer } from "./HelpDrawer";
import { Notifications } from "./Notifications";
import { TitleSlotContext } from "./TitleSlot";

/** Each role sees only the screens it needs (permissions come from the API). */
const NAV = [
  { to: "/", label: "Corbeille", icon: Inbox, permission: "cases.read" },
  { to: "/pilotage", label: "Pilotage", icon: Gauge, permission: "pilotage.read" },
  { to: "/journal", label: "Audit", icon: ScrollText, permission: "audit.read" },
  { to: "/ia", label: "IA", icon: BrainCircuit, permission: "eval.read" },
  { to: "/aide", label: "Aide", icon: BookOpen, permission: null },
] as const;

export function AppShell() {
  const s = useSession();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const path = useRouterState({ select: (r) => r.location.pathname });
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (!s) navigate({ to: "/connexion" });
  }, [s, navigate]);
  // "?" opens the help for the current screen, like F1 in desktop software.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
      if (e.key === "?" && !typing) setHelpOpen((v) => !v);
      if (e.key === "Escape") setHelpOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (!s) return null;

  const items = NAV.filter((n) => n.permission === null || s.user.permissions.includes(n.permission));
  const initials = s.user.name.slice(0, 2).toUpperCase();

  function logout() {
    session.set(null);
    qc.clear();
  }

  return (
    <div className="flex h-full lg:p-3 print:block print:p-0">
      {/* --- dark icon rail ------------------------------------------------------------ */}
      <aside className="flex w-[84px] shrink-0 flex-col items-center py-4 text-white print:hidden" aria-label="Navigation">
        <Link to={s.user.home} className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-p-cream text-sm font-black tracking-tight text-rail"
              title="Tri & Mesure — accueil de votre rôle">
          T&amp;M
        </Link>
        <nav className="flex flex-1 flex-col items-center gap-1.5" aria-label="Navigation principale">
          {items.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="group relative flex w-16 flex-col items-center gap-1 rounded-2xl py-2 text-white/60 transition-colors hover:bg-rail-hover hover:text-white"
              activeProps={{ className: "!text-white bg-rail-hover", "aria-current": "page" }}
              activeOptions={{ exact: to === "/" }}
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute -left-[10px] top-2 bottom-2 w-1 rounded-full bg-brand-red" aria-hidden />}
                  <Icon size={21} aria-hidden />
                  <span className="text-xs font-medium leading-none">{label}</span>
                </>
              )}
            </Link>
          ))}
        </nav>
        <button type="button" onClick={logout} title="Changer de rôle"
                className="flex w-16 flex-col items-center gap-1 rounded-2xl py-2 text-white/60 hover:bg-rail-hover hover:text-white">
          <LogOut size={20} aria-hidden />
          <span className="text-xs font-medium leading-none">Rôle</span>
        </button>
      </aside>

      {/* --- white panel ----------------------------------------------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white shadow-soft lg:rounded-[28px] print:rounded-none print:shadow-none">
        <header className="flex items-center gap-4 px-6 pb-2 pt-5 lg:px-8 print:hidden">
          <div ref={setSlot} className="min-w-0 flex-1" />
          <button type="button" onClick={() => setHelpOpen(true)}
                  className="grid h-10 w-10 place-items-center rounded-full bg-surface text-ink hover:bg-accent-soft hover:text-accent"
                  title="Comment marche cet écran ? (touche ?)" aria-label="Aide sur cet écran">
            <CircleHelp size={19} aria-hidden />
          </button>
          <Notifications />
          <div className="flex items-center gap-2.5 rounded-full bg-surface py-1 pl-1 pr-4">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-bold text-white" aria-hidden>
              {initials}
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-semibold">{s.user.name}</span>
              <span className="block text-xs text-muted">{s.user.role_label}</span>
            </span>
          </div>
        </header>
        <TitleSlotContext.Provider value={slot}>
          <main className={cn("min-h-0 flex-1 overflow-y-auto px-6 pb-8 pt-3 lg:px-8")}>
            <Outlet />
          </main>
        </TitleSlotContext.Provider>
        <footer className="border-t border-line px-8 py-2.5 text-xs text-muted print:hidden">
          Prototype étudiant non affilié à un assureur · données entièrement fictives · l'IA propose, un humain décide
        </footer>
      </div>
      <HelpDrawer open={helpOpen} onClose={() => setHelpOpen(false)} path={path} role={s.user.role} />
      <Toaster />
    </div>
  );
}
