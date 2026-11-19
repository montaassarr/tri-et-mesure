import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, BrainCircuit, Gauge, Inbox, ScrollText } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, unwrap } from "@/api/client";
import { useRoles } from "@/api/hooks";
import { Button, ErrorNotice, inputClass } from "@/components/ui";
import { cn } from "@/lib/utils";
import { session } from "./session";

type RoleCode = "gestionnaire" | "responsable" | "auditeur" | "equipe_ia";

const ROLE_UI: Record<RoleCode, { icon: typeof Inbox; name: string; tile: string }> = {
  gestionnaire: { icon: Inbox, name: "Sophie", tile: "bg-p-sky" },
  responsable: { icon: Gauge, name: "Inès", tile: "bg-p-mint" },
  auditeur: { icon: ScrollText, name: "Paul", tile: "bg-p-cream" },
  equipe_ia: { icon: BrainCircuit, name: "Lucas", tile: "bg-p-lavender" },
};


export function LoginPage() {
  const roles = useRoles();
  const navigate = useNavigate();
  const [role, setRole] = useState<RoleCode>("gestionnaire");
  const [name, setName] = useState(ROLE_UI.gestionnaire.name);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = unwrap(await api.POST("/api/auth/demo-login", { body: { name, role } }));
      session.set({ token: res.access_token, expiresAt: res.expires_at, user: res.user });
      navigate({ to: res.user.home });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full p-3 sm:p-6">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl overflow-hidden rounded-[32px] bg-white shadow-soft lg:grid-cols-[0.9fr_1.1fr]">
        {/* left: the promise */}
        <section className="relative flex flex-col justify-between overflow-hidden bg-rail p-10 text-white">
          <div aria-hidden className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-[64px] border border-white/10" />
          <div aria-hidden className="pointer-events-none absolute -bottom-10 right-16 h-56 w-56 rounded-[48px] border border-white/10" />
          <div className="relative">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-p-cream text-sm font-black text-rail">T&amp;M</span>
            <h1 className="mt-8 text-4xl font-extrabold leading-tight tracking-tight">
              Tri <span className="text-brand-red">&amp;</span> Mesure
            </h1>
            <p className="mt-3 max-w-sm text-lg text-white/80">L'IA propose. Un humain décide. L'outil mesure.</p>
          </div>
          <p className="relative mt-10 text-sm text-white/50">
            Prototype étudiant non affilié à un assureur · données entièrement fictives
          </p>
        </section>

        {/* right: choose a role */}
        <form onSubmit={submit} className="flex flex-col justify-center p-8 sm:p-12">
          <h2 className="text-3xl font-extrabold tracking-tight">Qui êtes-vous ?</h2>
          <div role="radiogroup" aria-label="Rôle" className="mt-6 grid gap-3 sm:grid-cols-2">
            {(roles.data ?? []).map((r) => {
              const code = r.code as RoleCode;
              const ui = ROLE_UI[code];
              const Icon = ui.icon;
              const selected = role === code;
              return (
                <button key={code} type="button" role="radio" aria-checked={selected}
                        onClick={() => { setRole(code); setName(ui.name); }}
                        className={cn("rounded-3xl p-5 text-left transition-all", ui.tile,
                          selected ? "ring-2 ring-accent ring-offset-2" : "opacity-90 hover:opacity-100")}>
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-accent shadow-soft">
                    <Icon size={20} aria-hidden />
                  </span>
                  <div className="mt-3 font-bold">{r.label}</div>
                  <div className="mt-1 text-sm text-ink/70">{r.mission}</div>
                </button>
              );
            })}
          </div>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex-1 text-sm">
              <span className="font-semibold">Prénom</span>
              <input className={cn(inputClass, "mt-1")} value={name} onChange={(e) => setName(e.target.value)}
                     minLength={2} maxLength={40} required />
            </label>
            <Button type="submit" size="lg" disabled={busy || name.trim().length < 2}>
              Entrer <ArrowRight size={18} aria-hidden />
            </Button>
          </div>
          {error !== null && <div className="mt-3"><ErrorNotice error={error} /></div>}
          <p className="mt-5 text-sm text-muted">Démo sans mot de passe.</p>
        </form>
      </div>
    </div>
  );
}
