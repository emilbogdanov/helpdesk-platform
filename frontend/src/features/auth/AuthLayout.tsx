import { Navigate, Outlet, useSearchParams } from "react-router";

import styles from "@/features/auth/AuthLayout.module.css";
import { safeNextPath } from "@/features/auth/redirect";
import { useSessionState } from "@/features/auth/session-context";

export function AuthLayout() {
  const { session } = useSessionState();
  const [params] = useSearchParams();

  if (session) {
    return <Navigate to={safeNextPath(params.get("next"))} replace />;
  }

  return (
    <div className={styles.page}>
      <main className={styles.panel}>
        <p className={styles.wordmark}>Helpdesk</p>
        <Outlet />
      </main>
    </div>
  );
}
