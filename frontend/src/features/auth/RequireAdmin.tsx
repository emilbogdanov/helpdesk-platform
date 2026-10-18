import { Link, Outlet } from "react-router";

import { useCurrentUserProfile } from "@/features/auth/current-user";
import { PageState } from "@/ui/PageState";

// Hiding the links isn't protection, the API refuses non-admins anyway; this gives anyone
// who follows an old link a clear answer instead of a page of errors.
export function RequireAdmin() {
  const user = useCurrentUserProfile();
  if (user.role !== "admin") {
    return (
      <PageState title="Only admins can open this page">
        <p>Ask an admin if you need something changed here.</p>
        <Link to="/tickets">Back to tickets</Link>
      </PageState>
    );
  }
  return <Outlet />;
}
