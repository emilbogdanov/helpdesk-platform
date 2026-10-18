import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { unwrap } from "@/api/client";
import { useApi } from "@/api/context";
import type { components } from "@/api/schema";
import type { TicketSort, TicketStatus, Visibility } from "@/api/types";

export type NewTicket = components["schemas"]["OpenTicketRequest"];

export interface TicketFilters {
  statuses: readonly TicketStatus[];
  sort: TicketSort;
}

const PAGE_SIZE = 25;

export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (filters: TicketFilters) => [...ticketKeys.lists(), filters] as const,
  detail: (ticketId: string) => [...ticketKeys.all, "detail", ticketId] as const,
  comments: (ticketId: string) => [...ticketKeys.detail(ticketId), "comments"] as const,
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
