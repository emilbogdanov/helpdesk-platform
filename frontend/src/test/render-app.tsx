import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";

import { createApiClient } from "@/api/client";
import { AppProviders } from "@/app/AppProviders";
import { routes } from "@/app/routes";
import { SessionStore, sessionMiddleware } from "@/features/auth/session";
import { FakeHelpdesk } from "@/test/fake-helpdesk";
import type { Account } from "@/test/fixtures";
import { server } from "@/test/server";

interface RenderAppOptions {
  signedInAs?: Account;
  // A token the API no longer accepts, as after a deactivation or a rotated secret.
  withRejectedToken?: boolean;
  helpdesk?: FakeHelpdesk;
}

// The whole app, routes and all, against the fake backend: tests drive it like a user would.
export function renderApp(path: string, options: RenderAppOptions = {}) {
  const helpdesk = options.helpdesk ?? new FakeHelpdesk();
  server.use(...helpdesk.handlers());

  const session = new SessionStore(sessionStorage);
  const expiresAt = new Date(Date.now() + 15 * 60 * 1000);
  if (options.signedInAs) {
    session.start(helpdesk.issueToken(options.signedInAs.user), expiresAt);
  } else if (options.withRejectedToken) {
    session.start("token-the-api-no-longer-accepts", expiresAt);
  }
  const api = createApiClient({ baseUrl: `${location.origin}/api` });
  api.use(sessionMiddleware(session));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });

  render(
    <AppProviders api={api} session={session} queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );

  return { user: userEvent.setup(), router, session, helpdesk };
}
