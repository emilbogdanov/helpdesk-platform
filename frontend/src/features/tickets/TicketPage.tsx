import { Link, useParams } from "react-router";

import { ApiError } from "@/api/client";
import type { Ticket, User } from "@/api/types";
import { useCurrentUserProfile } from "@/features/auth/current-user";
import { useTicket } from "@/features/tickets/api";
import { Conversation } from "@/features/tickets/Conversation";
import { FirstResponseNote } from "@/features/tickets/FirstResponseNote";
import { audienceFor, type Audience } from "@/features/tickets/labels";
import { PriorityLabel } from "@/features/tickets/PriorityLabel";
import { ReplyForm } from "@/features/tickets/ReplyForm";
import { StatusBadge } from "@/features/tickets/StatusBadge";
import { TicketControls } from "@/features/tickets/TicketControls";
import styles from "@/features/tickets/TicketPage.module.css";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/ui/Button";
import { classNames } from "@/ui/class-names";
import { PageState } from "@/ui/PageState";

export function TicketPage() {
  const { ticketId = "" } = useParams();
  const user = useCurrentUserProfile();
  const ticket = useTicket(ticketId);

  if (ticket.isPending) {
    return <PageState title="Loading ticket…" busy />;
  }
  if (ticket.isError) {
    // A customer gets the same 404 for someone else's ticket as for one that doesn't exist.
    if (ticket.error instanceof ApiError && ticket.error.status === 404) {
      return (
        <PageState title="Ticket not found">
          <p>It may have been mistyped, or it belongs to another account.</p>
          <Link to="/tickets">Back to tickets</Link>
        </PageState>
      );
    }
    return (
      <PageState title="Couldn't load this ticket">
        <p>The helpdesk didn't answer. Try again in a moment.</p>
        <Button onClick={() => void ticket.refetch()}>Try again</Button>
      </PageState>
    );
  }

  return <TicketView ticket={ticket.data} viewer={user} audience={audienceFor(user.role)} />;
}

function TicketView({
  ticket,
  viewer,
  audience,
}: {
  ticket: Ticket;
  viewer: User;
  audience: Audience;
}) {
  const isStaff = audience === "staff";

  return (
    <article
      className={classNames(styles.page, isStaff && styles.withPanel)}
      aria-labelledby="ticket-subject"
    >
      <div className={styles.main}>
        <Link to="/tickets" className={styles.back}>
          {isStaff ? "Queue" : "Tickets"}
        </Link>
        <header className={styles.header}>
          <h1 id="ticket-subject" className={styles.subject}>
            {ticket.subject}
          </h1>
          <dl className={styles.facts}>
            <div>
              <dt>Status</dt>
              <dd>
                <StatusBadge status={ticket.status} audience={audience} />
              </dd>
            </div>
            <div>
              <dt>Priority</dt>
              <dd>
                <PriorityLabel priority={ticket.priority} />
              </dd>
            </div>
            <div>
              <dt>Opened</dt>
              <dd>
                <time dateTime={ticket.created_at}>{formatDateTime(ticket.created_at)}</time>
                {isStaff && <> by {ticket.requester.display_name}</>}
              </dd>
            </div>
            {isStaff ? (
              <div>
                <dt>First reply</dt>
                <dd>
                  <FirstResponseNote ticket={ticket} />
                </dd>
              </div>
            ) : (
              <div>
                <dt>Handled by</dt>
                <dd className={ticket.assignee ? undefined : styles.muted}>
                  {ticket.assignee?.display_name ?? "Not picked up yet"}
                </dd>
              </div>
            )}
          </dl>
        </header>

        <section aria-label="Description" className={styles.description}>
          {ticket.description}
        </section>

        <Conversation ticketId={ticket.id} viewer={viewer} />
        <ReplyForm ticket={ticket} audience={audience} />
      </div>
      {isStaff && <TicketControls ticket={ticket} viewer={viewer} />}
    </article>
  );
}
