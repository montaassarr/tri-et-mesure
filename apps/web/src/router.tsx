import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from "@tanstack/react-router";
import { LoginPage } from "@/auth/LoginPage";
import { session } from "@/auth/session";
import { AppShell } from "@/components/shell/AppShell";
import { ErrorNotice } from "@/components/ui";
import { AiPage } from "@/features/ai/AiPage";
import { AuditPage } from "@/features/audit/AuditPage";
import { ReportPage } from "@/features/audit/ReportPage";
import { CasePage } from "@/features/case/CasePage";
import { HelpPage } from "@/features/help/HelpPage";
import { PilotagePage } from "@/features/pilotage/PilotagePage";
import { QueuePage } from "@/features/queue/QueuePage";

/** Route guard: signed in, and allowed for this screen; otherwise go to the role's home. */
function guard(permission: string | null) {
  return () => {
    const s = session.get();
    if (!s) throw redirect({ to: "/connexion" });
    if (permission && !s.user.permissions.includes(permission)) {
      throw redirect({ to: s.user.home });
    }
  };
}

const rootRoute = createRootRoute({
  component: Outlet,
  errorComponent: ({ error }) => (
    <div className="mx-auto max-w-xl p-8">
      <ErrorNotice error={error} />
    </div>
  ),
});

const login = createRoute({
  getParentRoute: () => rootRoute,
  path: "/connexion",
  component: LoginPage,
});

const app = createRoute({ getParentRoute: () => rootRoute, id: "app", component: AppShell });

const queue = createRoute({
  getParentRoute: () => app,
  path: "/",
  beforeLoad: guard("cases.read"),
  component: QueuePage,
});
const dossier = createRoute({
  getParentRoute: () => app,
  path: "/dossier/$id",
  beforeLoad: guard("cases.read"),
  component: function Dossier() {
    const { id } = dossier.useParams();
    return <CasePage key={id} id={Number(id)} />;
  },
});
const pilotage = createRoute({
  getParentRoute: () => app,
  path: "/pilotage",
  beforeLoad: guard("pilotage.read"),
  component: PilotagePage,
});
const journal = createRoute({
  getParentRoute: () => app,
  path: "/journal",
  beforeLoad: guard("audit.read"),
  component: AuditPage,
});
const rapport = createRoute({
  getParentRoute: () => app,
  path: "/journal/rapport",
  beforeLoad: guard("audit.read"),
  component: ReportPage,
});
const ia = createRoute({
  getParentRoute: () => app,
  path: "/ia",
  beforeLoad: guard("eval.read"),
  component: AiPage,
});
const aide = createRoute({
  getParentRoute: () => app,
  path: "/aide",
  beforeLoad: guard(null),
  component: HelpPage,
});

const routeTree = rootRoute.addChildren([
  login,
  app.addChildren([queue, dossier, pilotage, journal, rapport, ia, aide]),
]);

export const router = createRouter({ routeTree, defaultPreload: "intent" });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
