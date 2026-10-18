import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { yTicks } from "@/features/admin/ActivityChart";
import { FakeHelpdesk } from "@/test/fake-helpdesk";
import { elena, maria, nadia, petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";
import { minutesAgo } from "@/test/time";

function busyFortnight(): FakeHelpdesk {
  const helpdesk = new FakeHelpdesk();
  helpdesk.seedTicket({
    subject: "Payments page shows a blank screen",
    requester: nadia,
    priority: "urgent",
    breachedAt: minutesAgo(30),
    createdAt: minutesAgo(120),
  });
  helpdesk.seedTicket({ subject: "CSV export stops at 10,000 rows", requester: petar });
  helpdesk.seedTicket({
    subject: "Invoice PDF shows last month's VAT rate",
    requester: petar,
    status: "waiting_on_customer",
    assignee: elena,
    createdAt: minutesAgo(300),
    firstRespondedAt: minutesAgo(250),
  });
  helpdesk.seedTicket({
    subject: "Can't change the billing email",
    requester: petar,
    status: "resolved",
    assignee: elena,
    createdAt: minutesAgo(3000),
    firstRespondedAt: minutesAgo(2900),
    resolvedAt: minutesAgo(60),
  });
  return helpdesk;
}

function tile(label: string): HTMLElement {
  const term = screen.getByText(label, { selector: "dt" });
  const box = term.parentElement;
  if (!box) throw new Error(`no tile for ${label}`);
  return box;
}

describe("the dashboard", () => {
  it("sums up the queue as it stands", async () => {
    renderApp("/admin", { signedInAs: maria, helpdesk: busyFortnight() });

    await screen.findByText("Open", { selector: "dt" });

    expect(within(tile("Open")).getByText("2")).toBeVisible();
    expect(within(tile("Waiting on customer")).getByText("1")).toBeVisible();
    expect(within(tile("Unassigned")).getByText("2")).toBeVisible();
    expect(within(tile("Awaiting a first reply")).getByText("1 past the target")).toBeVisible();
    // Replies after 50 and 100 minutes.
    expect(within(tile("Median first reply")).getByText("1 h 15 min")).toBeVisible();
  });

  it("charts each day and keeps the numbers in a table", async () => {
    const { user } = renderApp("/admin", { signedInAs: maria, helpdesk: busyFortnight() });
    const legend = within(await screen.findByRole("list", { name: "Legend" }));
    expect(legend.getByText("Opened").parentElement).toHaveTextContent("Opened 4");
    expect(legend.getByText("Resolved").parentElement).toHaveTextContent("Resolved 1");

    await user.click(screen.getByText("Show the numbers"));
    const table = within(screen.getByRole("table"));

    expect(table.getAllByRole("row")).toHaveLength(15);
    const today = new Date().toISOString().slice(0, 10);
    expect(table.getByRole("row", { name: new RegExp(today) })).toHaveTextContent(
      /^\S+\s*[1-4]\s*[01]$/,
    );
  });

  it("shows a day's figures on hover or keyboard focus", async () => {
    renderApp("/admin", { signedInAs: maria, helpdesk: busyFortnight() });
    const days = await screen.findAllByRole("img", { name: /opened, \d+ resolved$/ });

    fireEvent.focus(days.at(-1) ?? document.body);

    expect(screen.getByText("opened", { exact: false, selector: "p" })).toBeVisible();
  });

  it("changes the period", async () => {
    const { user, router } = renderApp("/admin", { signedInAs: maria, helpdesk: busyFortnight() });

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Period" }),
      "Last 7 days",
    );

    expect(await screen.findAllByRole("img", { name: /resolved$/ })).toHaveLength(7);
    expect(router.state.location.search).toBe("?days=7");
  });

  it("is for admins only", async () => {
    renderApp("/admin", { signedInAs: elena });

    expect(await screen.findByText("Only admins can open this page")).toBeVisible();
  });
});

describe("yTicks", () => {
  it.each([
    [0, [0, 1, 2, 3, 4]],
    [7, [0, 2, 4, 6, 8]],
    [23, [0, 5, 10, 15, 20, 25]],
    [120, [0, 25, 50, 75, 100, 125]],
  ])("spaces the axis for a peak of %i", (max, expected) => {
    expect(yTicks(max)).toEqual(expected);
  });
});
