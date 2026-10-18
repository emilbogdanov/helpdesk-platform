import { useMutation, useQuery } from "@tanstack/react-query";

import { unwrap, type ApiClient } from "@/api/client";
import { useApi } from "@/api/context";
import type { components } from "@/api/schema";
import type { User } from "@/api/types";
import type { SessionStore } from "@/features/auth/session";
import { useSessionState, useSessionStore } from "@/features/auth/session-context";

export type Credentials = components["schemas"]["TokenRequest"];
export type SignUpDetails = components["schemas"]["SignUpRequest"];

export const currentUserKey = ["users", "me"] as const;

export function useCurrentUser() {
  const api = useApi();
  const { session } = useSessionState();
  return useQuery({
    queryKey: currentUserKey,
    queryFn: (): Promise<User> => unwrap(api.GET("/users/me")),
    enabled: session !== null,
  });
}

export function useSignIn() {
  const api = useApi();
  const store = useSessionStore();
  return useMutation({
    mutationFn: (credentials: Credentials) => signIn(api, store, credentials),
  });
}

export function useSignUp() {
  const api = useApi();
  const store = useSessionStore();
  return useMutation({
    mutationFn: async (details: SignUpDetails) => {
      await unwrap(api.POST("/auth/sign-up", { body: details }));
      // Straight in after signing up, rather than making the customer type it all again.
      await signIn(api, store, { email: details.email, password: details.password });
    },
  });
}

async function signIn(api: ApiClient, store: SessionStore, credentials: Credentials) {
  const token = await unwrap(api.POST("/auth/token", { body: credentials }));
  store.start(token.access_token, new Date(token.expires_at));
}
