import { screen, waitFor, within } from "@testing-library/react";
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
    expect(screen.getByRole("combobox", { name: "Status" })).toHaveDisplayValue(
      "Waiting on customer",
    );
  });
});

describe("a ticket, worked by staff", () => {
  function unassignedTicket() {
    const helpdesk = new FakeHelpdesk();
    const ticket = helpdesk.seedTicket({
      subject: "CSV export stops at 10,000 rows",
      requester: nadia,
      priority: "normal",
    });
    return { helpdesk, ticket };
  }

  function options(name: string): string[] {
    const select = screen.getByRole("combobox", { name });
    return within(select)
      .getAllByRole("option")
      .filter((option) => option instanceof HTMLOptionElement && !option.disabled)
      .map((option) => option.textContent);
  }

  it("lets an agent take a ticket and start work on it", async () => {
    const { helpdesk, ticket } = unassignedTicket();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });
    await screen.findByRole("complementary", { name: "Ticket properties" });
    expect(options("Status")).toEqual(["Open", "Resolved", "Closed"]);
    expect(screen.getByText("Assign someone to start work on it.")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Take it" }));
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Assignee" })).toHaveDisplayValue(
        "Elena Dimitrova (you)",
      );
    });
    await user.selectOptions(screen.getByRole("combobox", { name: "Status" }), "In progress");

    await waitFor(() => {
      expect(helpdesk.tickets[0]?.status).toBe("in_progress");
    });
    expect(screen.queryByRole("button", { name: "Take it" })).not.toBeInTheDocument();
    expect(options("Status")).toEqual(["In progress", "Open", "Waiting on customer", "Resolved"]);
  });

  it("hands a ticket to a colleague", async () => {
    const { helpdesk, ticket } = unassignedTicket();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });
    const assignee = await screen.findByRole("combobox", { name: "Assignee" });
    await waitFor(() => {
      expect(options("Assignee")).toEqual(["Unassigned", "Elena Dimitrova (you)", "Maria Ivanova"]);
    });

    await user.selectOptions(assignee, "Maria Ivanova");

    await waitFor(() => {
      expect(helpdesk.tickets[0]?.assignee?.display_name).toBe("Maria Ivanova");
    });
    expect(assignee).toHaveDisplayValue("Maria Ivanova");
  });

  it("raises the priority", async () => {
    const { helpdesk, ticket } = unassignedTicket();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });

    await user.selectOptions(await screen.findByRole("combobox", { name: "Priority" }), "Urgent");

    await waitFor(() => {
      expect(helpdesk.tickets[0]?.priority).toBe("urgent");
    });
    expect(screen.getByText("Due in 1 hour")).toBeVisible();
  });

  it("explains and reloads when someone else changed the ticket first", async () => {
    const { helpdesk, ticket } = unassignedTicket();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });
    const priority = await screen.findByRole("combobox", { name: "Priority" });
    helpdesk.conflictOnNextChange();
    // Meanwhile a colleague bumped it to high.
    ticket.priority = "high";

    await user.selectOptions(priority, "Urgent");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Someone else changed this ticket at the same moment.",
    );
    await waitFor(() => {
      expect(priority).toHaveDisplayValue("High");
    });
  });

  it("writes internal notes that the customer never sees", async () => {
    const { helpdesk, ticket } = unassignedTicket();
    const { user } = renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });
    await screen.findByRole("complementary", { name: "Ticket properties" });

    await user.click(screen.getByRole("radio", { name: "Internal note" }));
    await user.type(
      screen.getByRole("textbox", { name: "Internal note" }),
      "Reproduced on staging, limit is in the exporter.",
    );
    await user.click(screen.getByRole("button", { name: "Add note" }));

    const note = await (await conversation()).findByText(/Reproduced on staging/);
    expect(
      within(note.closest("article") ?? document.body).getByText("Internal note"),
    ).toBeVisible();
    expect(helpdesk.comments.get(ticket.id)?.[0]?.visibility).toBe("internal");
  });

  it("keeps a closed ticket's properties read-only", async () => {
    const helpdesk = new FakeHelpdesk();
    const ticket = helpdesk.seedTicket({
      subject: "Duplicate of the CSV export ticket",
      requester: nadia,
      status: "closed",
    });
    renderApp(`/tickets/${ticket.id}`, { signedInAs: elena, helpdesk });

    expect(await screen.findByRole("combobox", { name: "Status" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Priority" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Assignee" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Take it" })).not.toBeInTheDocument();
  });
});
