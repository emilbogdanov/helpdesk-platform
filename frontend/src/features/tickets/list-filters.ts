import type { Priority, TicketSort, TicketStatus } from "@/api/types";
import type { TicketFilters } from "@/features/tickets/api";
import { priorities, type Audience } from "@/features/tickets/labels";

export const statusViews = [
  { id: "active", label: "Active", statuses: ["open", "in_progress", "waiting_on_customer"] },
  { id: "resolved", label: "Resolved", statuses: ["resolved"] },
  { id: "closed", label: "Closed", statuses: ["closed"] },
  { id: "all", label: "All", statuses: [] },
] as const satisfies readonly { id: string; label: string; statuses: readonly TicketStatus[] }[];

export type StatusView = (typeof statusViews)[number];

const sorts: readonly TicketSort[] = ["newest", "oldest", "recently_updated"];
const assignees = ["me", "unassigned"] as const;

// Filters live in the URL, so a reload, the back button or a pasted link shows the same list.
// Staff work the queue oldest first; customers care about what changed most recently.
export function filtersFromSearch(
  search: URLSearchParams,
  audience: Audience,
): { view: StatusView; filters: TicketFilters } {
  const view = statusViews.find(({ id }) => id === search.get("view")) ?? statusViews[0];
  const defaultSort = audience === "staff" ? "oldest" : "recently_updated";
  const sort = sorts.find((option) => option === search.get("sort")) ?? defaultSort;
  if (audience === "requester") {
    return { view, filters: { statuses: view.statuses, sort } };
  }
  const priority: Priority | null =
    priorities.find((option) => option === search.get("priority")) ?? null;
  const assignee = assignees.find((option) => option === search.get("assignee")) ?? null;
  return { view, filters: { statuses: view.statuses, sort, priority, assignee } };
}
