import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { FakeHelpdesk } from "@/test/fake-helpdesk";
import { petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

describe("opening a ticket", () => {
  it("opens the ticket and shows it", async () => {
    const helpdesk = new FakeHelpdesk();
    const { user, router } = renderApp("/tickets/new", { signedInAs: petar, helpdesk });

    await user.type(
      await screen.findByLabelText("Subject"),
      "Checkout returns 500 when the cart has a gift card",
    );
    await user.type(
      screen.getByLabelText("What happened?"),
      "Every order with a gift card fails at the payment step.",
    );
    await user.selectOptions(screen.getByLabelText("Priority"), "High");
    expect(screen.getByText("Support aims to reply within 4 hours.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Open ticket" }));

    expect(
      await screen.findByRole("heading", {
        name: "Checkout returns 500 when the cart has a gift card",
      }),
    ).toBeVisible();
    expect(helpdesk.tickets).toHaveLength(1);
    expect(helpdesk.tickets[0]?.priority).toBe("high");
    expect(router.state.location.pathname).toBe(`/tickets/${helpdesk.tickets[0]?.id ?? ""}`);
  });

  it("sends the same idempotency key when the customer retries", async () => {
    const keys: (string | null)[] = [];
    const helpdesk = new FakeHelpdesk();
    const { user } = renderApp("/tickets/new", {
      signedInAs: petar,
      helpdesk,
      overrides: [
        http.post("/api/tickets", ({ request }) => {
          keys.push(request.headers.get("Idempotency-Key"));
          // The first attempt's connection drops; later ones go through to the backend.
          return keys.length === 1 ? HttpResponse.error() : undefined;
        }),
      ],
    });

    await user.type(await screen.findByLabelText("Subject"), "Refund for order 1042");
    await user.type(screen.getByLabelText("What happened?"), "I was charged twice.");
    await user.click(screen.getByRole("button", { name: "Open ticket" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your text is still here");
    await user.click(screen.getByRole("button", { name: "Open ticket" }));

    await screen.findByRole("heading", { name: "Refund for order 1042" });
    expect(keys).toHaveLength(2);
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys[1]).toBe(keys[0]);
    expect(helpdesk.tickets).toHaveLength(1);
  });

  it("passes on why the API rejected the ticket", async () => {
    const { user } = renderApp("/tickets/new", { signedInAs: petar });

    await user.type(await screen.findByLabelText("Subject"), "   ");
    await user.type(screen.getByLabelText("What happened?"), "The dashboard is blank.");
    await user.click(screen.getByRole("button", { name: "Open ticket" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Subject must not be blank.");
  });
});
