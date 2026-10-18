import type { Priority, Ticket } from "@/api/types";

// Mirrors the backend's first-response targets (domain/tickets/sla.py), so the queue can say
// how long is left before the worker flags a ticket.
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
