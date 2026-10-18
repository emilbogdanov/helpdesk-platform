import { useNavigate, useSearchParams } from "react-router";

import type { TicketSort } from "@/api/types";
import { useCurrentUserProfile } from "@/features/auth/current-user";
import { useTicketList } from "@/features/tickets/api";
import { audienceFor } from "@/features/tickets/labels";
import { filtersFromSearch, statusViews } from "@/features/tickets/list-filters";
import { QueueFilters } from "@/features/tickets/QueueFilters";
import styles from "@/features/tickets/TicketListPage.module.css";
import { TicketTable } from "@/features/tickets/TicketTable";
import { Button, ButtonLink } from "@/ui/Button";
import { classNames } from "@/ui/class-names";
import { useHotkeys } from "@/lib/use-hotkeys";
import { PageState } from "@/ui/PageState";

export function TicketListPage() {
  const user = useCurrentUserProfile();
  const audience = audienceFor(user.role);
  const [search, setSearch] = useSearchParams();
  const { view, filters } = filtersFromSearch(search, audience);
  const list = useTicketList(filters);
  const navigate = useNavigate();
  const isCustomer = audience === "requester";

  useHotkeys({
    c: isCustomer
      ? () => {
          void navigate("/tickets/new");
        }
      : undefined,
  });

  function update(changes: Record<string, string>) {
    setSearch((current) => {
      const next = new URLSearchParams(current);
      for (const [key, value] of Object.entries(changes)) {
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
      }
      return next;
    });
  }

  const tickets = list.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section className={styles.page} aria-labelledby="tickets-heading">
      <div className={styles.header}>
        <h1 id="tickets-heading" className={styles.heading}>
          {isCustomer ? "Your tickets" : "Queue"}
        </h1>
        {isCustomer && (
          <ButtonLink
            to="/tickets/new"
            variant="primary"
            aria-keyshortcuts="c"
            title="New ticket (C)"
          >
            New ticket
          </ButtonLink>
        )}
      </div>

      <div className={styles.toolbar}>
        <div role="group" aria-label="Show tickets" className={styles.views}>
          {statusViews.map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={option.id === view.id}
              className={classNames(styles.view, option.id === view.id && styles.currentView)}
              onClick={() => {
                update({ view: option.id });
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        {!isCustomer && <QueueFilters filters={filters} onChange={update} />}
      </div>

      {list.isPending ? (
        <PageState title="Loading tickets…" busy />
      ) : list.isError ? (
        <PageState title="Couldn't load tickets">
          <p>The helpdesk didn't answer. Try again in a moment.</p>
          <Button onClick={() => void list.refetch()}>Try again</Button>
        </PageState>
      ) : tickets.length === 0 ? (
        <EmptyList viewId={view.id} isCustomer={isCustomer} />
      ) : (
        <>
          <TicketTable
            tickets={tickets}
            audience={audience}
            sort={filters.sort}
            onSort={(sort: TicketSort) => {
              update({ sort });
            }}
          />
          <p className={styles.shortcuts}>
            <kbd>j</kbd> and <kbd>k</kbd> move through the list, <kbd>Enter</kbd> opens a ticket
            {isCustomer && (
              <>
                , <kbd>c</kbd> starts a new one
              </>
            )}
            .
          </p>
          {list.hasNextPage && (
            <div className={styles.more}>
              <Button onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>
                {list.isFetchingNextPage ? "Loading…" : "Show more"}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function EmptyList({ viewId, isCustomer }: { viewId: string; isCustomer: boolean }) {
  if (viewId === "active" || viewId === "all") {
    return isCustomer ? (
      <PageState
        title={viewId === "all" ? "You haven't opened any tickets" : "Nothing open right now"}
      >
        <p>When something isn't working, open a ticket and the support team will pick it up.</p>
        <ButtonLink to="/tickets/new" variant="primary">
          New ticket
        </ButtonLink>
      </PageState>
    ) : (
      <PageState title="No tickets here">
        <p>Nothing matches this view.</p>
      </PageState>
    );
  }
  return (
    <PageState title={viewId === "resolved" ? "No resolved tickets" : "No closed tickets"}>
      <p>Tickets move here once support marks them {viewId}.</p>
    </PageState>
  );
}
