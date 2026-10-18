import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { unwrap } from "@/api/client";
import { useApi } from "@/api/context";
import type { components } from "@/api/schema";
import type { Role } from "@/api/types";

export type NewPerson = components["schemas"]["CreateUserRequest"];
export type TicketStats = components["schemas"]["TicketStatsResponse"];

export interface PeopleFilters {
  search: string;
  role: Role | null;
  status: "active" | "deactivated" | null;
}

const PAGE_SIZE = 50;

export const adminKeys = {
  people: ["admin", "people"] as const,
  peopleList: (filters: PeopleFilters) => [...adminKeys.people, filters] as const,
  stats: (days: number) => ["admin", "stats", days] as const,
};

export function usePeople(filters: PeopleFilters) {
  const api = useApi();
  return useInfiniteQuery({
    queryKey: adminKeys.peopleList(filters),
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/users", {
          params: {
            query: {
              q: filters.search || null,
              role: filters.role,
              status: filters.status,
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

function useAccountMutation<Variables>(
  send: (api: ReturnType<typeof useApi>, variables: Variables) => Promise<unknown>,
) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: Variables) => send(api, variables),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.people }),
  });
}

export function useAddPerson() {
  return useAccountMutation((api, person: NewPerson) =>
    unwrap(api.POST("/users", { body: person })),
  );
}

export function useChangeRole() {
  return useAccountMutation((api, { userId, role }: { userId: string; role: Role }) =>
    unwrap(
      api.PUT("/users/{user_id}/role", { params: { path: { user_id: userId } }, body: { role } }),
    ),
  );
}

export function useSetActive() {
  return useAccountMutation((api, { userId, active }: { userId: string; active: boolean }) => {
    const path = { user_id: userId };
    return active
      ? unwrap(api.POST("/users/{user_id}/reactivate", { params: { path } }))
      : unwrap(api.POST("/users/{user_id}/deactivate", { params: { path } }));
  });
}

export function useTicketStats(days: number) {
  const api = useApi();
  return useQuery({
    queryKey: adminKeys.stats(days),
    queryFn: () => unwrap(api.GET("/stats/tickets", { params: { query: { days } } })),
    // Live enough for a dashboard left open on a second screen.
    refetchInterval: 60_000,
  });
}
