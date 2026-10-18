import { Navigate, Outlet, useLocation } from "react-router";

import { signInPathFor } from "@/features/auth/redirect";
import { useSessionState } from "@/features/auth/session-context";

export function RequireSession() {
  const { session, ended } = useSessionState();
  const location = useLocation();

  if (!session) {
    // After an expiry, come back to the same page; after signing out, start fresh.
    return <Navigate to={ended === "signed_out" ? "/sign-in" : signInPathFor(location)} replace />;
  }
  return <Outlet />;
}
