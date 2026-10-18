import type { Priority, Ticket, TicketStatus } from "@/api/types";

// Mirrors the backend's domain rules (domain/tickets/status.py and sla.py) so the UI only
// offers moves that can succeed. The server still checks every one of them.
export const nextStatuses: Record<TicketStatus, readonly TicketStatus[]> = {
  open: ["in_progress", "resolved", "closed"],
  in_progress: ["open", "waiting_on_customer", "resolved"],
  waiting_on_customer: ["in_progress", "resolved"],
  resolved: ["open", "closed"],
  closed: [],
};

export function needsAssignee(status: TicketStatus): boolean {
  return status === "in_progress" || status === "waiting_on_customer";
}

const HOUR = 60 * 60 * 1000;

export const firstResponseTargetMs: Record<Priority, number> = {
  urgent: HOUR,
  high: 4 * HOUR,
  normal: 24 * HOUR,
  low: 72 * HOUR,
};

export type FirstResponse =
  { state: "replied" } | { state: "not_needed" } | { state: "due" | "overdue"; dueAt: Date };

export function firstResponse(ticket: Ticket, now: Date = new Date()): FirstResponse {
  if (ticket.first_responded_at) {
    return { state: "replied" };
  }
  if (ticket.status === "resolved" || ticket.status === "closed") {
    return { state: "not_needed" };
  }
  const dueAt = new Date(
    new Date(ticket.created_at).getTime() + firstResponseTargetMs[ticket.priority],
  );
  // The worker flags breaches once a minute; the clock catches the ones in between.
  const overdue = ticket.sla_breached_at !== null || now >= dueAt;
  return { state: overdue ? "overdue" : "due", dueAt };
}
