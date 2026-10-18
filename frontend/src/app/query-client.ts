import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";

const MAX_RETRIES = 2;

export function shouldRetry(failureCount: number, error: Error): boolean {
  // A 4xx answer won't change on a second try; a dropped connection or a 5xx might.
  if (error instanceof ApiError && error.status < 500) {
    return false;
  }
  return failureCount < MAX_RETRIES;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 30_000 },
      // Writes aren't retried blindly; ticket creation has its own idempotency key for that.
      mutations: { retry: false },
    },
  });
}
