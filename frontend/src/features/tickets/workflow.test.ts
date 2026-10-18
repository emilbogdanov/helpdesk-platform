import { describe, expect, it } from "vitest";

import type { Ticket } from "@/api/types";
import { firstResponse } from "@/features/tickets/workflow";

const NOW = new Date("2026-10-18T14:00:00Z");

function ticket(overrides: Partial<Ticket>): Ticket {
  return {
    id: "5013d606-fa10-4d29-9850-c388206e56b8",
    requester: { id: "910d416c", display_name: "Petar Georgiev", role: "customer" },
    subject: "Checkout returns 500 when the cart has a gift card",
    description: "Every order with a gift card fails at the payment step.",
    priority: "high",
    status: "open",
    assignee: null,
    created_at: "2026-10-18T12:00:00Z",
    updated_at: "2026-10-18T12:00:00Z",
    resolved_at: null,
    closed_at: null,
    first_responded_at: null,
    sla_breached_at: null,
    ...overrides,
  };
}

describe("firstResponse", () => {
  it("counts the target from when the ticket was opened", () => {
    expect(firstResponse(ticket({ priority: "high" }), NOW)).toEqual({
      state: "due",
      dueAt: new Date("2026-10-18T16:00:00Z"),
    });
  });

  it("is overdue once the target passes, before the worker has flagged it", () => {
    expect(firstResponse(ticket({ priority: "urgent" }), NOW).state).toBe("overdue");
  });

  it("trusts the server's breach flag", () => {
    const flagged = ticket({ priority: "low", sla_breached_at: "2026-10-18T13:00:00Z" });

    expect(firstResponse(flagged, NOW).state).toBe("overdue");
  });

  it("stops counting once staff have replied, or the ticket is done", () => {
    expect(firstResponse(ticket({ first_responded_at: "2026-10-18T12:30:00Z" }), NOW)).toEqual({
      state: "replied",
    });
    expect(firstResponse(ticket({ status: "closed", priority: "urgent" }), NOW)).toEqual({
      state: "not_needed",
    });
  });
});
