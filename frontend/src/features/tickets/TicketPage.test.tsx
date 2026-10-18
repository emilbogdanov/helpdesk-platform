import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeHelpdesk, type SeededTicket } from "@/test/fake-helpdesk";
import { elena, nadia, petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

function ticketWithConversation(overrides: Partial<SeededTicket> = {}) {
  const helpdesk = new FakeHelpdesk();
  const ticket = helpdesk.seedTicket({
    subject: "Invoice PDF shows last month's VAT rate",
    description: "Invoice INV-2026-0412 lists 19% VAT. The rate changed to 20% on 1 October.",
    requester: petar,
    assignee: elena,
    status: "waiting_on_customer",
    priority: "high",
    ...overrides,
  });
  helpdesk.seedComment(ticket, elena, "Billing pushed the rate change late; checking.", true);
  helpdesk.seedComment(ticket, elena, "Could you tell me when you downloaded the PDF?");
  return { helpdesk, ticket };
}

// The conversation section appears once the comments have loaded.
async function conversation() {
  return within(await screen.findByRole("region", { name: "Conversation" }));
}

describe("a ticket", () => {
  it("shows its requester the details and the public conversation", async () => {
    const { helpdesk, ticket } = ticketWithConversation();
    renderApp(`/tickets/${ticket.id}`, { signedInAs: petar, helpdesk });

    expect(
      await screen.findByRole("heading", { name: "Invoice PDF shows last month's VAT rate" }),
    ).toBeVisible();
    expect(screen.getByText(/Invoice INV-2026-0412 lists 19% VAT/)).toBeVisible();
    expect(screen.getByText("Waiting on you")).toBeVisible();
    expect(screen.getByText("High")).toBeVisible();
    const thread = await conversation();
    expect(thread.getByText("Could you tell me when you downloaded the PDF?")).toBeVisible();
    expect(thread.getByText("Elena Dimitrova")).toBeVisible();
    expect(thread.getByText("Support")).toBeVisible();
    expect(thread.queryByText(/Billing pushed the rate change late/)).not.toBeInTheDocument();
  });

  it("puts the ticket back in progress when its requester replies", async () => {
    const { helpdesk, ticket } = ticketWithConversation();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: petar, helpdesk });
    expect(await screen.findByText(/Support is waiting for your reply/)).toBeVisible();

    await user.type(screen.getByLabelText("Your reply"), "This morning, around 09:30.");
    await user.click(screen.getByRole("button", { name: "Send reply" }));

    const thread = await conversation();
    expect(await thread.findByText("This morning, around 09:30.")).toBeVisible();
    expect(thread.getByText("You")).toBeVisible();
    expect(await screen.findByText("In progress")).toBeVisible();
    expect(screen.getByLabelText("Your reply")).toHaveValue("");
  });

  it("tells the requester a reply reopens a resolved ticket", async () => {
    const { helpdesk, ticket } = ticketWithConversation({ status: "resolved" });
    renderApp(`/tickets/${ticket.id}`, { signedInAs: petar, helpdesk });

    expect(await screen.findByText(/reply and the ticket reopens/)).toBeVisible();
  });

  it("takes no replies once closed", async () => {
    const { helpdesk, ticket } = ticketWithConversation({ status: "closed" });
    renderApp(`/tickets/${ticket.id}`, { signedInAs: petar, helpdesk });

    expect(await screen.findByText(/This ticket is closed/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Open a new ticket" })).toBeVisible();
    expect(screen.queryByLabelText("Your reply")).not.toBeInTheDocument();
  });

  it("is not found for another customer", async () => {
    const { helpdesk, ticket } = ticketWithConversation();
    renderApp(`/tickets/${ticket.id}`, { signedInAs: nadia, helpdesk });

    expect(await screen.findByText("Ticket not found")).toBeVisible();
  });

  it("shows staff the internal notes, marked as such", async () => {
    const { helpdesk, ticket } = ticketWithConversation();
    renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });

    const note = (await conversation()).getByText("Billing pushed the rate change late; checking.");
    expect(
      within(note.closest("article") ?? document.body).getByText("Internal note"),
    ).toBeVisible();
    expect(screen.getByText("Waiting on customer")).toBeVisible();
  });
});
