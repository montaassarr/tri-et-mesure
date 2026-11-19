import createClient, { type Middleware } from "openapi-fetch";
import { session } from "@/auth/session";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type QueueItem = Schemas["QueueItem"];
export type CaseDetail = Schemas["CaseDetail"];
export type Suggestion = Schemas["SuggestionOut"];
export type ReviewIn = Schemas["ReviewIn"];
export type Meta = Schemas["Meta"];
export type AuditEvent = Schemas["AuditEventOut"];
export type EvalRun = Schemas["EvalRunOut"];
export type AIConfig = Schemas["AIConfigOut"];
export type Role = Schemas["RoleOut"];

/** Adds the bearer token; on 401 the session is cleared and the UI goes back to login. */
const auth: Middleware = {
  onRequest({ request }) {
    const s = session.get();
    if (s) request.headers.set("Authorization", `Bearer ${s.token}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401 && session.get()) session.set(null);
    return response;
  },
};

/** Typed client generated from the FastAPI OpenAPI spec (`pnpm gen:api`). */
export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL ?? "" });
api.use(auth);

/** Errors follow RFC 9457 Problem Details: `detail` is a French sentence the UI can show. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message);
  }
}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    if (result.response.status === 204) return undefined as T;
    const e = (result.error ?? {}) as { detail?: string; title?: string; request_id?: string };
    throw new ApiError(
      e.detail ?? e.title ?? `Erreur ${result.response.status}`,
      result.response.status,
      e.request_id,
    );
  }
  return result.data;
}
