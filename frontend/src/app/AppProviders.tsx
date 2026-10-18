import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import { ApiProvider } from "@/api/context";
import type { SessionStore } from "@/features/auth/session";
import { SessionProvider } from "@/features/auth/session-context";

interface AppProvidersProps {
  api: ApiClient;
  session: SessionStore;
  queryClient: QueryClient;
  children: ReactNode;
}

export function AppProviders({ api, session, queryClient, children }: AppProvidersProps) {
  // Nothing cached for one account may be shown to the next one to sign in.
  useEffect(
    () =>
      session.subscribe(() => {
        if (!session.current) {
          queryClient.clear();
        }
      }),
    [session, queryClient],
  );

  return (
    <ApiProvider client={api}>
      <SessionProvider store={session}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </SessionProvider>
    </ApiProvider>
  );
}
