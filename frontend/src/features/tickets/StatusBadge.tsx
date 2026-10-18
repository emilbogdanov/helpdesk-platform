import type { TicketStatus } from "@/api/types";
import styles from "@/features/tickets/StatusBadge.module.css";
import { statusLabel, type Audience } from "@/features/tickets/labels";
import { classNames } from "@/ui/class-names";

interface StatusBadgeProps {
  status: TicketStatus;
  audience: Audience;
}

export function StatusBadge({ status, audience }: StatusBadgeProps) {
  return (
    <span className={classNames(styles.badge, styles[status])}>
      {statusLabel(status, audience)}
    </span>
  );
}
