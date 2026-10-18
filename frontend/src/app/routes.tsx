import { Navigate, type RouteObject } from "react-router";

import { NotFoundPage } from "@/app/NotFoundPage";
import { RouteError } from "@/app/RouteError";
import { AccountPage } from "@/features/account/AccountPage";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { RequireSession } from "@/features/auth/RequireSession";
import { SignInPage } from "@/features/auth/SignInPage";
import { SignUpPage } from "@/features/auth/SignUpPage";
import { TicketListPage } from "@/features/tickets/TicketListPage";
import { AppShell } from "@/layout/AppShell";

export const routes: RouteObject[] = [
  {
    errorElement: <RouteError />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: "sign-in", element: <SignInPage /> },
          { path: "sign-up", element: <SignUpPage /> },
        ],
      },
      {
        element: <RequireSession />,
        children: [
          {
            element: <AppShell />,
            children: [
              { index: true, element: <Navigate to="/tickets" replace /> },
              { path: "tickets", element: <TicketListPage /> },
              { path: "account", element: <AccountPage /> },
              { path: "*", element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
];
