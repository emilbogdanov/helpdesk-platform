import type { Priority } from "@/api/types";
import { priorityLabels } from "@/features/tickets/labels";
import styles from "@/features/tickets/PriorityLabel.module.css";
import { classNames } from "@/ui/class-names";

export function PriorityLabel({ priority }: { priority: Priority }) {
  return (
    <span className={classNames(styles.priority, styles[priority])}>
      {priorityLabels[priority]}
    </span>
  );
}
