import type { TicketFilters } from "@/features/tickets/api";
import { priorities, priorityLabels } from "@/features/tickets/labels";
import styles from "@/features/tickets/QueueFilters.module.css";

interface QueueFiltersProps {
  filters: TicketFilters;
  onChange: (changes: Record<string, string>) => void;
}

export function QueueFilters({ filters, onChange }: QueueFiltersProps) {
  return (
    <div className={styles.filters}>
      <label className={styles.filter}>
        Assignee
        <select
          value={filters.assignee ?? ""}
          onChange={(event) => {
            onChange({ assignee: event.target.value });
          }}
        >
          <option value="">Anyone</option>
          <option value="me">Me</option>
          <option value="unassigned">Unassigned</option>
        </select>
      </label>
      <label className={styles.filter}>
        Priority
        <select
          value={filters.priority ?? ""}
          onChange={(event) => {
            onChange({ priority: event.target.value });
          }}
        >
          <option value="">Any</option>
          {[...priorities].reverse().map((priority) => (
            <option key={priority} value={priority}>
              {priorityLabels[priority]}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
