import type { ReactNode } from "react";

import styles from "@/ui/Notice.module.css";
import { classNames } from "@/ui/class-names";

interface NoticeProps {
  tone: "danger" | "info";
  children: ReactNode;
}

// Errors interrupt (role="alert"); informational notes wait their turn (role="status").
export function Notice({ tone, children }: NoticeProps) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={classNames(styles.notice, styles[tone])}
    >
      {children}
    </div>
  );
}
