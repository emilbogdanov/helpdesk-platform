import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeHelpdesk } from "@/test/fake-helpdesk";
import { elena, maria } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

describe("the signed-in app", () => {
  it("sends visitors who aren't signed in to the sign-in page", async () => {
    const { router } = renderApp("/account");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/sign-in");
  });

  it("shows who is signed in, and signs them out", async () => {
    const { user, router } = renderApp("/", { signedInAs: elena });

    const header = await screen.findByRole("banner");
    expect(within(header).getByRole("link", { name: "Elena Dimitrova Agent" })).toBeInTheDocument();

    await user.click(within(header).getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
    expect(sessionStorage.getItem("helpdesk.session")).toBeNull();
  });

  it("offers a retry when the account can't be loaded", async () => {
    const helpdesk = new FakeHelpdesk();
    helpdesk.failNextProfileRequests(1);
    const { user } = renderApp("/account", { signedInAs: maria, helpdesk });

    await user.click(await screen.findByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
  });

  it("shows a not-found page for addresses that don't exist", async () => {
    renderApp("/tickets/archive", { signedInAs: elena });

    expect(await screen.findByText("There's nothing at this address")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });
});
