import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

describe("signing in", () => {
  it("opens the page the visitor was trying to reach", async () => {
    const { user, router } = renderApp("/account");

    await user.type(await screen.findByLabelText("Email"), petar.user.email);
    await user.type(screen.getByLabelText("Password"), petar.password);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/account");
  });

  it("says so when the email and password don't match", async () => {
    const { user } = renderApp("/sign-in");

    await user.type(screen.getByLabelText("Email"), petar.user.email);
    await user.type(screen.getByLabelText("Password"), "winter-orchard-41");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email and password don't match an active account.",
    );
  });

  it("ignores a next link that points at another site", async () => {
    const { user, router } = renderApp("/sign-in?next=//evil.example/phish");

    await user.type(screen.getByLabelText("Email"), petar.user.email);
    await user.type(screen.getByLabelText("Password"), petar.password);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await screen.findByRole("heading", { name: "Account" });
    expect(router.state.location.pathname).toBe("/account");
  });

  it("explains an expired session and returns to the same page afterwards", async () => {
    const { user, router } = renderApp("/account?tab=security", { withRejectedToken: true });

    expect(await screen.findByText(/^Your session expired\./)).toHaveAttribute("role", "status");
    expect(router.state.location.search).toBe(
      `?next=${encodeURIComponent("/account?tab=security")}`,
    );

    await user.type(screen.getByLabelText("Email"), petar.user.email);
    await user.type(screen.getByLabelText("Password"), petar.password);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await screen.findByRole("heading", { name: "Account" });
    expect(router.state.location.search).toBe("?tab=security");
  });

  it("sends someone who is already signed in past the form", async () => {
    const { router } = renderApp("/sign-in", { signedInAs: petar });

    await screen.findByRole("heading", { name: "Account" });
    expect(router.state.location.pathname).toBe("/account");
  });
});
