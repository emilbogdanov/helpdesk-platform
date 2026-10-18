import type { Ticket } from "@/api/types";
import styles from "@/features/tickets/FirstResponseNote.module.css";
import { firstResponse } from "@/features/tickets/workflow";
import { formatDateTime, formatRelative } from "@/lib/format";

// Whether staff still owe the customer a first reply, and by when.
export function FirstResponseNote({
  ticket,
  compact = false,
}: {
  ticket: Ticket;
  compact?: boolean;
}) {
  const response = firstResponse(ticket);
  switch (response.state) {
    case "replied":
      return <span className={styles.done}>Replied</span>;
    case "not_needed":
      return <span className={styles.done}>Not needed</span>;
    case "due":
    case "overdue": {
      const due = formatRelative(response.dueAt.toISOString());
      const overdue = response.state === "overdue";
      const text = compact
        ? overdue
          ? "Overdue"
          : `Due ${due}`
        : overdue
          ? `Overdue, was due ${due}`
          : `Due ${due}`;
      return (
        <time
          dateTime={response.dueAt.toISOString()}
          title={`Due ${formatDateTime(response.dueAt.toISOString())}`}
          className={overdue ? styles.overdue : styles.due}
        >
          {text}
        </time>
      );
    }
  }
}
