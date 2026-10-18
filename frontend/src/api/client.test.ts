import { describe, expect, it } from "vitest";

import { ApiError, createApiClient, unwrap } from "@/api/client";

function clientAnswering(response: Response) {
  return createApiClient({
    baseUrl: "http://helpdesk.test/api",
    fetch: () => Promise.resolve(response),
  });
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("unwrap", () => {
  it("returns the body of a successful response", async () => {
    const client = clientAnswering(
      json(200, {
        id: "9d1c4a0e-63b5-4f43-9a7e-1d1f0f5d2a10",
        email: "elena.dimitrova@northwind.test",
        display_name: "Elena Dimitrova",
        role: "agent",
        is_active: true,
        created_at: "2026-10-12T08:41:00Z",
      }),
    );

    const me = await unwrap(client.GET("/users/me"));

    expect(me.display_name).toBe("Elena Dimitrova");
  });

  it("rejects with the API's code and message when the API refuses", async () => {
    const client = clientAnswering(
      json(409, {
        detail: "cannot move a ticket from in_progress to closed",
        code: "invalid_status_transition",
      }),
    );

    const change = unwrap(
      client.PUT("/tickets/{ticket_id}/status", {
        params: { path: { ticket_id: "5013d606-fa10-4d29-9850-c388206e56b8" } },
        body: { status: "closed" },
      }),
    );

    await expect(change).rejects.toEqual(
      new ApiError(
        409,
        "invalid_status_transition",
        "cannot move a ticket from in_progress to closed",
      ),
    );
  });

  it("reports an answer that didn't come from the API as unexpected", async () => {
    const client = clientAnswering(
      new Response("<html><body>502 Bad Gateway</body></html>", {
        status: 502,
        statusText: "Bad Gateway",
        headers: { "Content-Type": "text/html" },
      }),
    );

    const error: unknown = await unwrap(client.GET("/users/me")).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 502,
      code: "unexpected_response",
      message: "502 Bad Gateway",
    });
  });
});
