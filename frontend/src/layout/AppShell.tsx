import { Link, NavLink, Outlet } from "react-router";

import type { Role } from "@/api/types";
import { useCurrentUser } from "@/features/auth/api";
import { CurrentUserProvider } from "@/features/auth/current-user";
import { useSessionStore } from "@/features/auth/session-context";
import { ThemeSelect } from "@/features/theme/ThemeSelect";
import styles from "@/layout/AppShell.module.css";
import { Button } from "@/ui/Button";
import { PageState } from "@/ui/PageState";

const roleLabels: Record<Role, string> = {
  customer: "Customer",
  agent: "Agent",
  admin: "Admin",
};

export function AppShell() {
  const session = useSessionStore();
  const currentUser = useCurrentUser();

  function signOut() {
    session.end("signed_out");
  }

  if (currentUser.isPending) {
    return <PageState title="Loading your account…" busy />;
  }
  if (currentUser.isError) {
    return (
      <PageState title="Couldn't load your account">
        <p>The helpdesk didn't answer. It may be restarting; try again in a moment.</p>
        <Button onClick={() => void currentUser.refetch()}>Try again</Button>
      </PageState>
    );
  }

  const user = currentUser.data;
  return (
    <CurrentUserProvider user={user}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <div className={styles.primary}>
            <Link to="/" className={styles.wordmark}>
              Helpdesk
            </Link>
            <nav aria-label="Main" className={styles.nav}>
              <NavLink to="/tickets" className={styles.navLink}>
                Tickets
              </NavLink>
            </nav>
          </div>
          <div className={styles.actions}>
            <ThemeSelect />
            <Link to="/account" className={styles.account}>
              <span className={styles.name}>{user.display_name}</span>{" "}
              <span className={styles.role}>{roleLabels[user.role]}</span>
            </Link>
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </header>
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </CurrentUserProvider>
  );
}
