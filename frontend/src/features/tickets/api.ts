import { useInfiniteQuery } from "@tanstack/react-query";

import { unwrap } from "@/api/client";
import { useApi } from "@/api/context";
import type { TicketSort, TicketStatus } from "@/api/types";

export interface TicketFilters {
  statuses: readonly TicketStatus[];
  sort: TicketSort;
}

const PAGE_SIZE = 25;

export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (filters: TicketFilters) => [...ticketKeys.lists(), filters] as const,
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
