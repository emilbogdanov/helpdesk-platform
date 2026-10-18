import { useRef } from "react";
import { Link } from "react-router";

import type { Ticket, TicketSort } from "@/api/types";
import { FirstResponseNote } from "@/features/tickets/FirstResponseNote";
import type { Audience } from "@/features/tickets/labels";
import { PriorityLabel } from "@/features/tickets/PriorityLabel";
import { StatusBadge } from "@/features/tickets/StatusBadge";
import styles from "@/features/tickets/TicketTable.module.css";
import { formatDateTime, formatRelative } from "@/lib/format";
import { useHotkeys } from "@/lib/use-hotkeys";

interface TicketTableProps {
  tickets: Ticket[];
  audience: Audience;
  sort: TicketSort;
  onSort: (sort: TicketSort) => void;
}

export function TicketTable({ tickets, audience, sort, onSort }: TicketTableProps) {
  const showPeople = audience === "staff";
  const table = useRef<HTMLTableElement>(null);

  // j and k walk the rows by moving focus between the subject links; Enter opens one.
  function moveFocus(step: 1 | -1) {
    const links = Array.from(table.current?.querySelectorAll<HTMLAnchorElement>("tbody a") ?? []);
    const current = links.findIndex((link) => link === document.activeElement);
    const next = current === -1 ? (step === 1 ? 0 : links.length - 1) : current + step;
    links[Math.min(Math.max(next, 0), links.length - 1)]?.focus();
  }

  useHotkeys({
    j: () => {
      moveFocus(1);
    },
    k: () => {
      moveFocus(-1);
    },
  });

  const openedSort = sort === "oldest" ? "ascending" : sort === "newest" ? "descending" : "none";

  return (
    <table ref={table} className={styles.table}>
      <thead>
        <tr>
          <th scope="col" className={styles.subject}>
            Subject
          </th>
          {showPeople && <th scope="col">Requester</th>}
          <th scope="col">Status</th>
          <th scope="col">Priority</th>
          {showPeople && <th scope="col">Assignee</th>}
          {showPeople && <th scope="col">First reply</th>}
          <th scope="col" aria-sort={openedSort}>
            <button
              type="button"
              className={styles.sortButton}
              onClick={() => {
                onSort(sort === "newest" ? "oldest" : "newest");
              }}
            >
              Opened
              <SortArrow direction={openedSort} />
            </button>
          </th>
          <th scope="col" aria-sort={sort === "recently_updated" ? "descending" : "none"}>
            <button
              type="button"
              className={styles.sortButton}
              onClick={() => {
                onSort("recently_updated");
              }}
            >
              Updated
              <SortArrow direction={sort === "recently_updated" ? "descending" : "none"} />
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        {tickets.map((ticket) => (
          <tr key={ticket.id}>
            <td className={styles.subject}>
              <Link to={`/tickets/${ticket.id}`} className={styles.subjectLink}>
                {ticket.subject}
              </Link>
            </td>
            {showPeople && <td>{ticket.requester.display_name}</td>}
            <td>
              <StatusBadge status={ticket.status} audience={audience} />
            </td>
            <td>
              <PriorityLabel priority={ticket.priority} />
            </td>
            {showPeople && (
              <td className={ticket.assignee ? undefined : styles.muted}>
                {ticket.assignee?.display_name ?? "Unassigned"}
              </td>
            )}
            {showPeople && (
              <td>
                <FirstResponseNote ticket={ticket} compact />
              </td>
            )}
            <td className={styles.time}>
              <Timestamp iso={ticket.created_at} />
            </td>
            <td className={styles.time}>
              <Timestamp iso={ticket.updated_at} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Timestamp({ iso }: { iso: string }) {
  return (
    <time dateTime={iso} title={formatDateTime(iso)}>
      {formatRelative(iso)}
    </time>
  );
}

function SortArrow({ direction }: { direction: "ascending" | "descending" | "none" }) {
  if (direction === "none") {
    return null;
  }
  return (
    <span aria-hidden="true" className={styles.arrow}>
      {direction === "ascending" ? "↑" : "↓"}
    </span>
  );
}
