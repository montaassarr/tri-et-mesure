/** Server state, one hook per use case. Components never call `api` directly. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type ReviewIn } from "./client";

const keys = {
  meta: ["meta"],
  cases: ["cases"],
  case: (id: number) => ["case", id],
  pilotage: ["pilotage"],
  assumptions: ["assumptions"],
  audit: (f: AuditFilters) => ["audit", f],
  register: ["register"],
  aiConfig: ["ai", "config"],
  quality: ["ai", "quality"],
  evals: ["ai", "evals"],
} as const;

// --- reference & auth ------------------------------------------------------------

export function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => unwrap(await api.GET("/api/auth/roles")),
    staleTime: Infinity,
  });
}

export function useMeta() {
  return useQuery({
    queryKey: keys.meta,
    queryFn: async () => unwrap(await api.GET("/api/meta")),
    staleTime: Infinity,
  });
}

// --- cases -----------------------------------------------------------------------

export function useCases() {
  return useQuery({
    queryKey: keys.cases,
    queryFn: async () => unwrap(await api.GET("/api/cases")),
    // While the worker is analysing, refresh so suggestions appear without a reload.
    refetchInterval: (q) =>
      q.state.data?.some((c) => c.analysis_status === "pending" || c.analysis_status === "running")
        ? 1500
        : 15_000,
  });
}

export function useCase(id: number) {
  return useQuery({
    queryKey: keys.case(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/cases/{case_id}", { params: { path: { case_id: id } } })),
    refetchInterval: (q) =>
      q.state.data?.analysis_status === "pending" || q.state.data?.analysis_status === "running"
        ? 1500
        : false,
  });
}

export function useNextCase() {
  return useMutation({
    mutationFn: async () => unwrap(await api.GET("/api/cases/next")).id,
  });
}

export function useClaim(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/cases/{case_id}/claim", { params: { path: { case_id: id } } }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(keys.case(id), data);
      qc.invalidateQueries({ queryKey: keys.cases });
    },
  });
}

export function useRelease(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/cases/{case_id}/release", { params: { path: { case_id: id } } }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.cases }),
  });
}

export function useReview(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ReviewIn) =>
      unwrap(
        await api.POST("/api/cases/{case_id}/review", {
          params: { path: { case_id: id } },
          body,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.cases });
      qc.invalidateQueries({ queryKey: keys.case(id) });
      qc.invalidateQueries({ queryKey: keys.pilotage });
    },
  });
}

export function useSeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/seed")),
    onSuccess: () => qc.invalidateQueries(),
  });
}

// --- manager ---------------------------------------------------------------------

export function usePilotage() {
  return useQuery({
    queryKey: keys.pilotage,
    queryFn: async () => unwrap(await api.GET("/api/pilotage")) as unknown as Pilotage,
    refetchInterval: 10_000,
  });
}

export function useAssumptions() {
  return useQuery({
    queryKey: keys.assumptions,
    queryFn: async () => unwrap(await api.GET("/api/assumptions")),
  });
}

export function useUpdateAssumption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, value }: { key: string; value: number }) =>
      unwrap(
        await api.PUT("/api/assumptions/{key}", { params: { path: { key } }, body: { value } }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.assumptions });
      qc.invalidateQueries({ queryKey: keys.pilotage });
    },
  });
}

// --- auditor ---------------------------------------------------------------------

export interface AuditFilters {
  type?: string;
  actor_kind?: "human" | "ai" | "system";
  email_id?: number;
}

export function useAudit(filters: AuditFilters) {
  return useQuery({
    queryKey: keys.audit(filters),
    queryFn: async () =>
      unwrap(await api.GET("/api/audit", { params: { query: { ...filters, limit: 200 } } })),
  });
}

export function useVerifyChain() {
  return useMutation({
    mutationFn: async () => unwrap(await api.GET("/api/audit/verify")),
  });
}

export function useRegister() {
  return useQuery({
    queryKey: keys.register,
    queryFn: async () => unwrap(await api.GET("/api/audit/register")) as unknown as Register,
  });
}

// --- AI team ---------------------------------------------------------------------

export function useAIConfig() {
  return useQuery({
    queryKey: keys.aiConfig,
    queryFn: async () => unwrap(await api.GET("/api/ai/config")),
    refetchInterval: (q) => ((q.state.data?.queue_depth ?? 0) > 0 ? 2000 : false),
  });
}

export function useUpdateAIConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      provider: "rules" | "anthropic" | "openai_compat";
      model?: string | null;
      prompt_version: string;
    }) => unwrap(await api.PUT("/api/ai/config", { body })),
    onSuccess: (data) => qc.setQueryData(keys.aiConfig, data),
  });
}

export function useReanalyze() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/ai/reanalyze-open")).count,
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useQuality() {
  return useQuery({
    queryKey: keys.quality,
    queryFn: async () => unwrap(await api.GET("/api/ai/quality")) as unknown as Quality,
  });
}

export function useEvalRuns() {
  return useQuery({
    queryKey: keys.evals,
    queryFn: async () => unwrap(await api.GET("/api/ai/eval-runs")),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });
}

export function useStartEval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      provider: "rules" | "anthropic" | "openai_compat";
      model?: string | null;
      dataset: "ci" | "dev" | "test";
    }) => unwrap(await api.POST("/api/ai/eval-runs", { body: { ...body, prompt_version: "v1" } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.evals }),
  });
}

// --- shapes of the free-form dashboard payloads ----------------------------------

export interface ArmStats {
  n: number;
  median_seconds: number | null;
  category_accuracy: number | null;
}

export interface Pilotage {
  stock: {
    open: number;
    by_priority: Record<string, number>;
    late: number;
    late_by_priority: Record<string, number>;
    due_soon: number;
    waiting_analysis: number;
    analysis_failed: number;
  };
  flow: {
    closed_total: number;
    closed_today: number;
    within_target_rate: number | null;
    manual_rate: number | null;
  };
  ai_value: {
    arms: { ai: ArmStats; control: ArmStats };
    enough_data: boolean;
    min_per_arm: number;
    seconds_saved_per_case: number | null;
    accepted_as_is_rate: number | null;
    cost_eur_per_email: number;
  };
  estimate: {
    monthly_hours_saved: number | null;
    monthly_value_eur: number | null;
    monthly_model_cost_eur: number;
    formula: string;
    warning: string;
  };
  sla_targets_hours: Record<string, number>;
  privacy_note: string;
}

export interface Quality {
  reviews: number;
  per_item: Record<string, { accepted: number; edited: number; rejected: number }>;
  by_model_and_prompt: Record<
    string,
    { n: number; category_accepted: number; category_acceptance_rate: number | null }
  >;
  rejection_reasons: Record<string, number>;
  calls: {
    total: number;
    model_calls: number;
    schema_valid_rate: number | null;
    fallback_rate: number | null;
    cost_eur_total: number;
    latency_p50_ms: number | null;
    latency_p95_ms: number | null;
    cache_read_tokens: number;
  };
}

export interface Register {
  purpose: string;
  data_categories: string[];
  minimisation: {
    masked_before_model: string[];
    not_masked: string[];
    masked_entities_total: Record<string, number>;
  };
  retention: {
    raw_text_days: number;
    raw_text_still_stored: number;
    raw_text_purged: number;
    kept: string;
  };
  recipients: { model_providers_used: string[]; what_they_receive: string };
  access: Record<string, string[]>;
  system_actors: Record<string, string>;
  audit: { events: number; chain_ok: boolean };
  decisions_by_ai: string;
}

// --- control tower (AI sources) ----------------------------------------------------

export interface SourceScore {
  code: string;
  name: string;
  kind: "internal" | "external";
  active: boolean;
  champion: boolean;
  suggestions: number;
  coverage: number | null;
  scored_cases: number;
  shown_to_handlers: number;
  category_agreement: number | null;
  category_agreement_unbiased: number | null;
  unbiased_cases: number;
  field_agreement: number | null;
  ground_truth_accuracy: number | null;
  cost_eur_per_suggestion: number | null;
  latency_p50_ms: number | null;
}

export function useSources() {
  return useQuery({
    queryKey: ["ai", "sources"],
    queryFn: async () => unwrap(await api.GET("/api/ai/sources")) as unknown as SourceScore[],
    refetchInterval: 5000,
  });
}

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => unwrap(await api.POST("/api/ai/sources", { body: { name } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai", "sources"] }),
  });
}

export function useToggleSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ code, active }: { code: string; active: boolean }) =>
      unwrap(await api.PUT("/api/ai/sources/{code}", { params: { path: { code } }, body: { active } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai", "sources"] }),
  });
}

export function useSetChampion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (source: string) =>
      unwrap(await api.PUT("/api/ai/champion", { body: { source } })),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useAlerts(enabled = true) {
  return useQuery({
    queryKey: ["ai", "alerts"],
    queryFn: async () => unwrap(await api.GET("/api/ai/alerts")),
    refetchInterval: 10_000,
    enabled,
  });
}

// --- storm mode ----------------------------------------------------------------------

export interface CrisisReport {
  id: number;
  name: string;
  kind: string;
  kind_label: string;
  started_at: string;
  ended_at: string | null;
  received: number;
  open: number;
  closed: number;
  late: number;
  urgent_open: number;
  waiting_analysis: number;
  closed_last_hour: number;
  hours_to_clear: number | null;
  median_seconds: { ai: number | null; control: number | null };
}

export function useCrisis(enabled = true) {
  return useQuery({
    queryKey: ["crisis"],
    queryFn: async () => unwrap(await api.GET("/api/crisis")) as unknown as CrisisReport | null,
    refetchInterval: 3000,
    enabled,
  });
}

export function useStartCrisis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; kind: "grele" | "tempete" | "inondation"; volume: number }) =>
      unwrap(await api.POST("/api/crisis", { body })) as unknown as CrisisReport,
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useEndCrisis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.POST("/api/crisis/{event_id}/end", { params: { path: { event_id: id } } })),
    onSuccess: () => qc.invalidateQueries(),
  });
}

// --- oversight report ----------------------------------------------------------------

export interface OversightReport {
  period: { from: string; to: string; days: number };
  generated_by: string;
  decisions: {
    total: number;
    by_authenticated_human: number;
    with_ai_proposal: number;
    without_ai_control_arm: number;
    manual_handling: number;
    ai_accepted_as_is: number;
    corrections_by_item: Record<string, number>;
    rejection_reasons: Record<string, number>;
    reviewers: number;
  };
  ai_systems: {
    suggestions_by_system: Record<string, number>;
    shown_to_handlers_by_system: Record<string, number>;
    fallbacks_to_rules: number;
    analysis_failures: number;
  };
  changes: { ts: string; type: string; actor: string; payload: Record<string, unknown> }[];
  privacy: { emails_masked: number; raw_text_purges: number; what_vendors_receive: string };
  integrity: {
    chain_ok: boolean;
    events_checked: number;
    events_in_period: number;
    seal_seq: number | null;
    seal_hash: string | null;
  };
  statement: string;
}

export function useOversightReport(days: number) {
  return useQuery({
    queryKey: ["report", days],
    queryFn: async () =>
      unwrap(await api.GET("/api/audit/report", { params: { query: { days } } })) as unknown as OversightReport,
    staleTime: Infinity,
  });
}

// --- handler workspace context ------------------------------------------------------

export interface PlaybookParams {
  category: string;
  numero_contrat?: string | null;
  type_dommage?: string | null;
  besoin_relogement?: boolean | null;
  fuite_active?: boolean | null;
  personne_vulnerable?: boolean | null;
}

export function usePlaybook(p: PlaybookParams) {
  const query = Object.fromEntries(
    Object.entries(p).filter(([, v]) => v !== null && v !== undefined && v !== ""),
  ) as Record<string, string | boolean>;
  return useQuery({
    queryKey: ["playbook", query],
    queryFn: async () =>
      unwrap(await api.GET("/api/playbook", { params: { query: query as never } })),
    enabled: Boolean(p.category),
    placeholderData: (prev) => prev,
  });
}

export function usePolicy(number: string | null, vehicle: boolean, damage: string | null) {
  return useQuery({
    queryKey: ["policy", number, vehicle, damage],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/policies/{number}", {
          params: { path: { number: number! }, query: { vehicle, ...(damage ? { damage: damage as never } : {}) } },
        }),
      ),
    enabled: Boolean(number && number.length >= 4),
  });
}

export function useRelated(id: number, contract: string | null) {
  return useQuery({
    queryKey: ["related", id, contract],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/cases/{case_id}/related", {
          params: { path: { case_id: id }, query: contract ? { contract } : {} },
        }),
      ),
  });
}

export function useTimeline(id: number) {
  return useQuery({
    queryKey: ["timeline", id],
    queryFn: async () =>
      unwrap(await api.GET("/api/cases/{case_id}/timeline", { params: { path: { case_id: id } } })),
  });
}
