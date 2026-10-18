import { Link } from "react-router";

import type { Ticket, TicketSort } from "@/api/types";
import type { Audience } from "@/features/tickets/labels";
import { PriorityLabel } from "@/features/tickets/PriorityLabel";
import { StatusBadge } from "@/features/tickets/StatusBadge";
import styles from "@/features/tickets/TicketTable.module.css";
import { formatDateTime, formatRelative } from "@/lib/format";

interface TicketTableProps {
  tickets: Ticket[];
  audience: Audience;
  sort: TicketSort;
  onSort: (sort: TicketSort) => void;
}

export function TicketTable({ tickets, audience, sort, onSort }: TicketTableProps) {
  const showPeople = audience === "staff";
  const openedSort = sort === "oldest" ? "ascending" : sort === "newest" ? "descending" : "none";

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col" className={styles.subject}>
            Subject
          </th>
          {showPeople && <th scope="col">Requester</th>}
          <th scope="col">Status</th>
          <th scope="col">Priority</th>
          {showPeople && <th scope="col">Assignee</th>}
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
