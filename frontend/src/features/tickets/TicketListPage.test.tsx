import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { FakeHelpdesk } from "@/test/fake-helpdesk";
import { elena, nadia, petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";
import { minutesAgo } from "@/test/time";

function subjectsInTable(): string[] {
  const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
  return rows.map((row) => within(row).getAllByRole("cell")[0]?.textContent ?? "");
}

function helpdeskWithPetarsTickets(): FakeHelpdesk {
  const helpdesk = new FakeHelpdesk();
  helpdesk.seedTicket({
    subject: "Invoice PDF shows last month's VAT rate",
    requester: petar,
    createdAt: minutesAgo(600),
    updatedAt: minutesAgo(120),
  });
  helpdesk.seedTicket({
    subject: "Checkout returns 500 when the cart has a gift card",
    requester: petar,
    status: "in_progress",
    assignee: elena,
    createdAt: minutesAgo(300),
    updatedAt: minutesAgo(10),
  });
  helpdesk.seedTicket({
    subject: "Can't change the billing email on my account",
    requester: petar,
    status: "resolved",
    createdAt: minutesAgo(4000),
  });
  helpdesk.seedTicket({ subject: "Export to CSV stops at 10,000 rows", requester: nadia });
  return helpdesk;
}

describe("the ticket list", () => {
  it("shows a customer their active tickets, most recently updated first", async () => {
    renderApp("/tickets", { signedInAs: petar, helpdesk: helpdeskWithPetarsTickets() });

    await screen.findByRole("table");

    expect(subjectsInTable()).toEqual([
      "Checkout returns 500 when the cart has a gift card",
      "Invoice PDF shows last month's VAT rate",
    ]);
    expect(screen.queryByRole("columnheader", { name: "Requester" })).not.toBeInTheDocument();
  });

  it("switches to resolved tickets and keeps the choice in the address", async () => {
    const { user, router } = renderApp("/tickets", {
      signedInAs: petar,
      helpdesk: helpdeskWithPetarsTickets(),
    });
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Resolved" }));

    expect(await screen.findByText("Can't change the billing email on my account")).toBeVisible();
    expect(subjectsInTable()).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Resolved" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(router.state.location.search).toBe("?view=resolved");
  });

  it("sorts by when tickets were opened, newest or oldest first", async () => {
    const { user } = renderApp("/tickets?view=all", {
      signedInAs: petar,
      helpdesk: helpdeskWithPetarsTickets(),
    });
    await screen.findByRole("table");
    const opened = () => screen.getByRole("columnheader", { name: /Opened/ });

    await user.click(within(opened()).getByRole("button"));
    expect(opened()).toHaveAttribute("aria-sort", "descending");
    expect(subjectsInTable()[0]).toBe("Checkout returns 500 when the cart has a gift card");

    await user.click(within(opened()).getByRole("button"));
    expect(opened()).toHaveAttribute("aria-sort", "ascending");
    expect(subjectsInTable()[0]).toBe("Can't change the billing email on my account");
  });

  it("loads more tickets on request", async () => {
    const helpdesk = new FakeHelpdesk();
    for (let n = 1; n <= 30; n += 1) {
      helpdesk.seedTicket({
        subject: `Order ${String(1000 + n)} arrived damaged`,
        requester: petar,
        createdAt: minutesAgo(n),
      });
    }
    const { user } = renderApp("/tickets", { signedInAs: petar, helpdesk });
    await screen.findByRole("table");
    expect(subjectsInTable()).toHaveLength(25);

    await user.click(screen.getByRole("button", { name: "Show more" }));

    await screen.findByText("Order 1030 arrived damaged");
    expect(subjectsInTable()).toHaveLength(30);
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("invites a customer without open tickets to open one", async () => {
    renderApp("/tickets", { signedInAs: nadia, helpdesk: new FakeHelpdesk() });

    expect(await screen.findByText("Nothing open right now")).toBeVisible();
    expect(screen.getAllByRole("link", { name: "New ticket" })).not.toHaveLength(0);
  });

  it("shows staff every customer's tickets with requester and assignee", async () => {
    renderApp("/tickets", { signedInAs: elena, helpdesk: helpdeskWithPetarsTickets() });

    expect(await screen.findByRole("heading", { name: "Queue" })).toBeVisible();
    const row = await screen.findByRole("row", { name: /Checkout returns 500/ });
    expect(within(row).getByText("Petar Georgiev")).toBeVisible();
    expect(within(row).getByText("Elena Dimitrova")).toBeVisible();
    expect(screen.getByText("Export to CSV stops at 10,000 rows")).toBeVisible();
  });

  it("offers a retry when the list can't be loaded", async () => {
    const { user } = renderApp("/tickets", {
      signedInAs: petar,
      helpdesk: helpdeskWithPetarsTickets(),
      overrides: [
        http.get("/api/tickets", () => new HttpResponse(null, { status: 503 }), { once: true }),
      ],
    });

    await user.click(await screen.findByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("table")).toBeVisible();
  });

  it("lets staff narrow the queue to unassigned urgent tickets", async () => {
    const helpdesk = helpdeskWithPetarsTickets();
    helpdesk.seedTicket({
      subject: "Payments page down for all customers",
      requester: nadia,
      priority: "urgent",
    });
    helpdesk.seedTicket({
      subject: "Refund stuck in pending",
      requester: nadia,
      priority: "urgent",
      assignee: elena,
      status: "in_progress",
    });
    const { user, router } = renderApp("/tickets", { signedInAs: elena, helpdesk });
    await screen.findByRole("table");

    await user.selectOptions(screen.getByLabelText("Assignee"), "Unassigned");
    await user.selectOptions(screen.getByLabelText("Priority"), "Urgent");

    await waitFor(() => {
      expect(subjectsInTable()).toEqual(["Payments page down for all customers"]);
    });
    expect(new URLSearchParams(router.state.location.search).get("assignee")).toBe("unassigned");
    expect(new URLSearchParams(router.state.location.search).get("priority")).toBe("urgent");
  });

  it("flags tickets whose first reply is overdue", async () => {
    const helpdesk = new FakeHelpdesk();
    helpdesk.seedTicket({
      subject: "Payments page down for all customers",
      requester: nadia,
      priority: "urgent",
      createdAt: minutesAgo(95),
    });
    helpdesk.seedTicket({
      subject: "Typo on the pricing page",
      requester: nadia,
      priority: "low",
      createdAt: minutesAgo(30),
    });
    renderApp("/tickets", { signedInAs: elena, helpdesk });

    const urgent = await screen.findByRole("row", { name: /Payments page down/ });
    expect(within(urgent).getByText("Overdue")).toBeVisible();
    const low = screen.getByRole("row", { name: /Typo on the pricing page/ });
    expect(within(low).getByText(/^Due in (2|3) days$/)).toBeVisible();
  });

  it("moves through tickets with j and k and opens one with Enter", async () => {
    const { user, router } = renderApp("/tickets", {
      signedInAs: petar,
      helpdesk: helpdeskWithPetarsTickets(),
    });
    await screen.findByRole("table");
    const checkout = screen.getByRole("link", { name: /Checkout returns 500/ });
    const invoice = screen.getByRole("link", { name: /Invoice PDF/ });

    await user.keyboard("j");
    expect(checkout).toHaveFocus();
    await user.keyboard("j");
    expect(invoice).toHaveFocus();
    await user.keyboard("k");
    expect(checkout).toHaveFocus();
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(router.state.location.pathname).toMatch(/^\/tickets\/[0-9a-f-]{36}$/);
    });
  });

  it("starts a new ticket when a customer presses c", async () => {
    const { user, router } = renderApp("/tickets", { signedInAs: nadia });
    await screen.findByText("Nothing open right now");

    await user.keyboard("c");

    expect(await screen.findByRole("heading", { name: "New ticket" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/tickets/new");
  });
});
