import type { TicketSort, TicketStatus } from "@/api/types";
import type { TicketFilters } from "@/features/tickets/api";

export const statusViews = [
  { id: "active", label: "Active", statuses: ["open", "in_progress", "waiting_on_customer"] },
  { id: "resolved", label: "Resolved", statuses: ["resolved"] },
  { id: "closed", label: "Closed", statuses: ["closed"] },
  { id: "all", label: "All", statuses: [] },
] as const satisfies readonly { id: string; label: string; statuses: readonly TicketStatus[] }[];

export type StatusView = (typeof statusViews)[number];

const sorts: readonly TicketSort[] = ["newest", "oldest", "recently_updated"];

// Filters live in the URL, so a reload, the back button or a pasted link shows the same list.
export function filtersFromSearch(search: URLSearchParams): {
  view: StatusView;
  filters: TicketFilters;
} {
  const view = statusViews.find(({ id }) => id === search.get("view")) ?? statusViews[0];
  const sort = sorts.find((option) => option === search.get("sort")) ?? "recently_updated";
  return { view, filters: { statuses: view.statuses, sort } };
}
