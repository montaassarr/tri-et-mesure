import { useSyncExternalStore } from "react";
import type { Schemas } from "@/api/client";

export type User = Schemas["UserOut"];
export interface Session {
  token: string;
  expiresAt: string;
  user: User;
}

const KEY = "tri-mesure:session";
const listeners = new Set<() => void>();

function load(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return new Date(s.expiresAt) > new Date() ? s : null;
  } catch {
    return null;
  }
}

let current: Session | null = load();

function emit() {
  listeners.forEach((l) => l());
}

/** Session kept per browser tab (sessionStorage), so two tabs can play two roles. */
export const session = {
  get: () => current,
  set(next: Session | null) {
    current = next;
    try {
      if (next) sessionStorage.setItem(KEY, JSON.stringify(next));
      else sessionStorage.removeItem(KEY);
    } catch {
      /* storage unavailable: keep in memory only */
    }
    emit();
  },
  can(permission: string) {
    return current?.user.permissions.includes(permission) ?? false;
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useSession(): Session | null {
  return useSyncExternalStore(session.subscribe, session.get);
}

export function useCan(permission: string): boolean {
  const s = useSession();
  return s?.user.permissions.includes(permission) ?? false;
}
