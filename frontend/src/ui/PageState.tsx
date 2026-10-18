import type { ReactNode } from "react";

import styles from "@/ui/PageState.module.css";

interface PageStateProps {
  title: string;
  children?: ReactNode;
  busy?: boolean;
}

// The one place a whole page says it's loading, empty, failed or off-limits.
export function PageState({ title, children, busy = false }: PageStateProps) {
  return (
    <div className={styles.state} role={busy ? "status" : undefined} aria-busy={busy || undefined}>
      <p className={styles.title}>{title}</p>
      {children && <div className={styles.body}>{children}</div>}
    </div>
  );
}
