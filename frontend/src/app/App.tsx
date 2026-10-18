import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";

import { createApiClient } from "@/api/client";
import { AppProviders } from "@/app/AppProviders";
import { createQueryClient } from "@/app/query-client";
import { routes } from "@/app/routes";
import { SessionStore, sessionMiddleware } from "@/features/auth/session";
import { browserStorage } from "@/lib/storage";

function createServices() {
  const session = new SessionStore(browserStorage("sessionStorage"));
  const api = createApiClient();
  api.use(sessionMiddleware(session));
  return { session, api, queryClient: createQueryClient(), router: createBrowserRouter(routes) };
}

export function App() {
  const [{ session, api, queryClient, router }] = useState(createServices);

  return (
    <AppProviders api={api} session={session} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
