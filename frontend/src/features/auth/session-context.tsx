import { createContext, use, useSyncExternalStore, type ReactNode } from "react";

import type { SessionState, SessionStore } from "@/features/auth/session";

const SessionContext = createContext<SessionStore | null>(null);

export function SessionProvider({ store, children }: { store: SessionStore; children: ReactNode }) {
  return <SessionContext value={store}>{children}</SessionContext>;
}

export function useSessionStore(): SessionStore {
  const store = use(SessionContext);
  if (!store) {
    throw new Error("useSessionStore needs a <SessionProvider> above it");
  }
  return store;
}

export function useSessionState(): SessionState {
  const store = useSessionStore();
  return useSyncExternalStore(store.subscribe, () => store.state);
}
