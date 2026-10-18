import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { unwrap } from "@/api/client";
import { useApi } from "@/api/context";
import type { components } from "@/api/schema";
import type { ApiClient } from "@/api/client";
import type { Priority, Ticket, TicketSort, TicketStatus, Visibility } from "@/api/types";

export type NewTicket = components["schemas"]["OpenTicketRequest"];

export interface TicketFilters {
  statuses: readonly TicketStatus[];
  sort: TicketSort;
  priority?: Priority | null;
  assignee?: "me" | "unassigned" | null;
}

const PAGE_SIZE = 25;

export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (filters: TicketFilters) => [...ticketKeys.lists(), filters] as const,
  detail: (ticketId: string) => [...ticketKeys.all, "detail", ticketId] as const,
  comments: (ticketId: string) => [...ticketKeys.detail(ticketId), "comments"] as const,
  staff: ["users", "staff"] as const,
};

export function useTicketList(filters: TicketFilters) {
  const api = useApi();
  return useInfiniteQuery({
    queryKey: ticketKeys.list(filters),
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/tickets", {
          params: {
            query: {
              status: [...filters.statuses],
              sort: filters.sort,
              priority: filters.priority ? [filters.priority] : [],
              assignee: filters.assignee ?? null,
              limit: PAGE_SIZE,
              cursor: pageParam,
            },
          },
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useTicket(ticketId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ticketKeys.detail(ticketId),
    queryFn: () =>
      unwrap(api.GET("/tickets/{ticket_id}", { params: { path: { ticket_id: ticketId } } })),
  });
}

export function useComments(ticketId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ticketKeys.comments(ticketId),
    queryFn: () =>
      unwrap(
        api.GET("/tickets/{ticket_id}/comments", { params: { path: { ticket_id: ticketId } } }),
      ),
  });
}

// The key is chosen once per form, so a resubmit after a timeout returns the ticket the
// first attempt created instead of opening a duplicate.
export function useOpenTicket(idempotencyKey: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticket: NewTicket) =>
      unwrap(
        api.POST("/tickets", {
          params: { header: { "Idempotency-Key": idempotencyKey } },
          body: ticket,
        }),
      ),
    onSuccess: (ticket) => {
      queryClient.setQueryData(ticketKeys.detail(ticket.id), ticket);
      void queryClient.invalidateQueries({ queryKey: ticketKeys.lists() });
    },
  });
}

export function useAddComment(ticketId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (comment: { body: string; visibility?: Visibility }) =>
      unwrap(
        api.POST("/tickets/{ticket_id}/comments", {
          params: { path: { ticket_id: ticketId } },
          body: comment,
        }),
      ),
    // A reply moves the ticket too: its updated time, and its status when the requester
    // answers (waiting -> in progress, resolved -> open).
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ticketKeys.detail(ticketId) }),
        queryClient.invalidateQueries({ queryKey: ticketKeys.lists() }),
      ]),
  });
}

export function useStaff() {
  const api = useApi();
  return useQuery({
    queryKey: ticketKeys.staff,
    queryFn: () => unwrap(api.GET("/users/staff")),
    // The team changes rarely; one fetch per session is plenty.
    staleTime: 10 * 60 * 1000,
  });
}

export type TicketChange =
  | { kind: "status"; status: TicketStatus }
  | { kind: "priority"; priority: Priority }
  | { kind: "assignee"; assigneeId: string | null }
  | { kind: "take" };

export function useChangeTicket(ticketId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: TicketChange) => sendChange(api, ticketId, change),
    onSuccess: (ticket) => {
      queryClient.setQueryData(ticketKeys.detail(ticketId), ticket);
      void queryClient.invalidateQueries({ queryKey: ticketKeys.lists() });
    },
  });
}

function sendChange(api: ApiClient, ticketId: string, change: TicketChange): Promise<Ticket> {
  const path = { ticket_id: ticketId };
  switch (change.kind) {
    case "status":
      return unwrap(
        api.PUT("/tickets/{ticket_id}/status", {
          params: { path },
          body: { status: change.status },
        }),
      );
    case "priority":
      return unwrap(
        api.PUT("/tickets/{ticket_id}/priority", {
          params: { path },
          body: { priority: change.priority },
        }),
      );
    case "assignee":
      return change.assigneeId === null
        ? unwrap(api.DELETE("/tickets/{ticket_id}/assignee", { params: { path } }))
        : unwrap(
            api.PUT("/tickets/{ticket_id}/assignee", {
              params: { path },
              body: { assignee_id: change.assigneeId },
            }),
          );
    case "take":
      return unwrap(api.POST("/tickets/{ticket_id}/take", { params: { path } }));
  }
}
