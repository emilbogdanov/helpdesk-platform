import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import { shouldRetry } from "@/app/query-client";

describe("shouldRetry", () => {
  it("gives up straight away on a client error", () => {
    expect(shouldRetry(0, new ApiError(404, "ticket_not_found", "ticket not found"))).toBe(false);
    expect(shouldRetry(0, new ApiError(401, "invalid_token", "access token expired"))).toBe(false);
  });

  it("retries server errors and dropped connections, but only twice", () => {
    const outage = new ApiError(503, "unexpected_response", "503 Service Unavailable");
    const offline = new TypeError("Failed to fetch");

    expect([0, 1, 2].map((failures) => shouldRetry(failures, outage))).toEqual([true, true, false]);
    expect([0, 1, 2].map((failures) => shouldRetry(failures, offline))).toEqual([
      true,
      true,
      false,
    ]);
  });
});
