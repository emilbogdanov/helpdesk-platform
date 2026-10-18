import { createContext, use, type ReactNode } from "react";

import type { ApiClient } from "@/api/client";

const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  return <ApiContext value={client}>{children}</ApiContext>;
}

export function useApi(): ApiClient {
  const client = use(ApiContext);
  if (!client) {
    throw new Error("useApi needs an <ApiProvider> above it");
  }
  return client;
}
