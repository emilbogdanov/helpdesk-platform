import type { Priority, Role, TicketStatus } from "@/api/types";

export type Audience = "requester" | "staff";

export function audienceFor(role: Role): Audience {
  return role === "customer" ? "requester" : "staff";
}

// The same state reads differently depending on whose move it is.
const statusLabels: Record<Audience, Record<TicketStatus, string>> = {
  requester: {
    open: "Open",
    in_progress: "In progress",
    waiting_on_customer: "Waiting on you",
    resolved: "Resolved",
    closed: "Closed",
  },
  staff: {
    open: "Open",
    in_progress: "In progress",
    waiting_on_customer: "Waiting on customer",
    resolved: "Resolved",
    closed: "Closed",
  },
};

export function statusLabel(status: TicketStatus, audience: Audience): string {
  return statusLabels[audience][status];
}

export const priorityLabels: Record<Priority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};
