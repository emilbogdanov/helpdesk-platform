import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";
import type { Ticket, User } from "@/api/types";
import { ticketKeys, useChangeTicket, useStaff, type TicketChange } from "@/features/tickets/api";
import { submitErrorMessage } from "@/features/tickets/errors";
import { priorities, priorityLabels, statusLabel } from "@/features/tickets/labels";
import styles from "@/features/tickets/TicketControls.module.css";
import { needsAssignee, nextStatuses } from "@/features/tickets/workflow";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { SelectField } from "@/ui/SelectField";

const UNASSIGNED = "";

// The staff side panel: who has the ticket, where it stands, how urgent it is.
export function TicketControls({ ticket, viewer }: { ticket: Ticket; viewer: User }) {
  const change = useChangeTicket(ticket.id);
  const staff = useStaff();
  const queryClient = useQueryClient();

  function apply(next: TicketChange) {
    change.mutate(next, {
      onError: (error) => {
        if (error instanceof ApiError && error.code === "concurrent_update") {
          void queryClient.invalidateQueries({ queryKey: ticketKeys.detail(ticket.id) });
        }
      },
    });
  }

  const reachable = nextStatuses[ticket.status].filter(
    (status) => ticket.assignee !== null || !needsAssignee(status),
  );
  const blockedByAssignee = nextStatuses[ticket.status].some(
    (status) => ticket.assignee === null && needsAssignee(status),
  );
  const closed = ticket.status === "closed";

  return (
    <aside className={styles.panel} aria-label="Ticket properties">
      {change.error && <Notice tone="danger">{submitErrorMessage(change.error)}</Notice>}

      <div className={styles.assignee}>
        <SelectField
          label="Assignee"
          value={ticket.assignee?.id ?? UNASSIGNED}
          disabled={closed || change.isPending || staff.isPending}
          onChange={(event) => {
            const assigneeId = event.target.value;
            apply({ kind: "assignee", assigneeId: assigneeId === UNASSIGNED ? null : assigneeId });
          }}
        >
          <option value={UNASSIGNED} disabled={needsAssignee(ticket.status)}>
            Unassigned
          </option>
          {staff.data?.map((person) => (
            <option key={person.id} value={person.id}>
              {person.id === viewer.id ? `${person.display_name} (you)` : person.display_name}
            </option>
          ))}
        </SelectField>
        {!closed && ticket.assignee?.id !== viewer.id && (
          <Button
            size="sm"
            disabled={change.isPending}
            onClick={() => {
              apply({ kind: "take" });
            }}
          >
            Take it
          </Button>
        )}
        {needsAssignee(ticket.status) && (
          <p className={styles.hint}>To release it, move it back to Open first.</p>
        )}
        {staff.isError && <p className={styles.hint}>Couldn't load the team list.</p>}
      </div>

      <SelectField
        label="Status"
        value={ticket.status}
        disabled={closed || change.isPending}
        hint={
          closed
            ? "Closed tickets stay closed."
            : blockedByAssignee
              ? "Assign someone to start work on it."
              : undefined
        }
        onChange={(event) => {
          const status = reachable.find((option) => option === event.target.value);
          if (status) {
            apply({ kind: "status", status });
          }
        }}
      >
        <option value={ticket.status}>{statusLabel(ticket.status, "staff")}</option>
        {reachable.map((status) => (
          <option key={status} value={status}>
            {statusLabel(status, "staff")}
          </option>
        ))}
      </SelectField>

      <SelectField
        label="Priority"
        value={ticket.priority}
        disabled={closed || change.isPending}
        onChange={(event) => {
          const priority = priorities.find((option) => option === event.target.value);
          if (priority) {
            apply({ kind: "priority", priority });
          }
        }}
      >
        {priorities.map((priority) => (
          <option key={priority} value={priority}>
            {priorityLabels[priority]}
          </option>
        ))}
      </SelectField>
    </aside>
  );
}
