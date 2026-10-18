import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeHelpdesk } from "@/test/fake-helpdesk";
import { elena, maria, nadia } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

function names(): string[] {
  const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
  return rows.map((row) => within(row).getAllByRole("rowheader")[0]?.firstChild?.textContent ?? "");
}

function row(name: string): HTMLElement {
  return screen.getByRole("row", { name: new RegExp(name) });
}

describe("the people page", () => {
  it("lists everyone by name with their role and status", async () => {
    renderApp("/admin/people", { signedInAs: maria });

    await screen.findByRole("table");

    expect(names()).toEqual([
      "Elena Dimitrova",
      "Maria Ivanova",
      "Nadia Petrova",
      "Petar Georgiev",
    ]);
    expect(within(row("Elena Dimitrova")).getByRole("combobox")).toHaveDisplayValue("Agent");
    expect(within(row("Nadia Petrova")).getByText("Active")).toBeVisible();
  });

  it("searches names and email addresses", async () => {
    const { user, router } = renderApp("/admin/people", { signedInAs: maria });
    await screen.findByRole("table");

    await user.type(
      screen.getByRole("searchbox", { name: "Search by name or email" }),
      "northwind",
    );

    await waitFor(() => {
      expect(names()).toEqual(["Elena Dimitrova", "Maria Ivanova"]);
    });
    expect(router.state.location.search).toBe("?q=northwind");
  });

  it("filters by role and status", async () => {
    const helpdesk = new FakeHelpdesk();
    const blocked = helpdesk.accounts.find((account) => account.user.id === nadia.user.id);
    if (blocked) blocked.user.is_active = false;
    const { user } = renderApp("/admin/people", { signedInAs: maria, helpdesk });
    await screen.findByRole("table");

    await user.selectOptions(screen.getByRole("combobox", { name: "Role" }), "Customers");
    await waitFor(() => {
      expect(names()).toEqual(["Nadia Petrova", "Petar Georgiev"]);
    });
    await user.selectOptions(screen.getByRole("combobox", { name: "Status" }), "Deactivated");

    await waitFor(() => {
      expect(names()).toEqual(["Nadia Petrova"]);
    });
    expect(within(row("Nadia Petrova")).getByRole("button", { name: "Reactivate" })).toBeVisible();
  });

  it("adds an agent who can sign in straight away", async () => {
    const helpdesk = new FakeHelpdesk();
    const { user } = renderApp("/admin/people", { signedInAs: maria, helpdesk });
    await user.click(await screen.findByRole("button", { name: "Add person" }));

    const form = within(screen.getByRole("form", { name: "Add a person" }));
    await user.type(form.getByLabelText("Name"), "Radoslav Petkov");
    await user.type(form.getByLabelText("Email"), "radoslav.petkov@northwind.test");
    await user.type(form.getByLabelText("Temporary password"), "first-shift-2026");
    await user.click(form.getByRole("button", { name: "Add person" }));

    expect(await screen.findByText("Radoslav Petkov can sign in now.")).toBeVisible();
    expect(await screen.findByRole("row", { name: /Radoslav Petkov/ })).toBeVisible();
    expect(helpdesk.accounts.at(-1)?.user.role).toBe("agent");
  });

  it("says when the email already has an account", async () => {
    const { user } = renderApp("/admin/people", { signedInAs: maria });
    await user.click(await screen.findByRole("button", { name: "Add person" }));

    const form = within(screen.getByRole("form", { name: "Add a person" }));
    await user.type(form.getByLabelText("Name"), "Elena Again");
    await user.type(form.getByLabelText("Email"), elena.user.email);
    await user.type(form.getByLabelText("Temporary password"), "first-shift-2026");
    await user.click(form.getByRole("button", { name: "Add person" }));

    expect(await form.findByRole("alert")).toHaveTextContent(
      "An account with this email already exists.",
    );
  });

  it("promotes an agent to admin", async () => {
    const helpdesk = new FakeHelpdesk();
    const { user } = renderApp("/admin/people", { signedInAs: maria, helpdesk });
    await screen.findByRole("table");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Role for Elena Dimitrova" }),
      "Admin",
    );

    await waitFor(() => {
      expect(helpdesk.accounts.find((a) => a.user.id === elena.user.id)?.user.role).toBe("admin");
    });
  });

  it("asks before deactivating someone, and can undo it", async () => {
    const helpdesk = new FakeHelpdesk();
    const { user } = renderApp("/admin/people", { signedInAs: maria, helpdesk });
    await screen.findByRole("table");

    await user.click(within(row("Elena Dimitrova")).getByRole("button", { name: "Deactivate" }));
    await user.click(
      within(row("Elena Dimitrova")).getByRole("button", {
        name: "Sign Elena out and deactivate",
      }),
    );

    expect(await within(row("Elena Dimitrova")).findByText("Deactivated")).toBeVisible();
    await user.click(within(row("Elena Dimitrova")).getByRole("button", { name: "Reactivate" }));
    expect(await within(row("Elena Dimitrova")).findByText("Active")).toBeVisible();
  });

  it("leaves the admin's own account alone", async () => {
    renderApp("/admin/people", { signedInAs: maria });
    await screen.findByRole("table");

    const own = row("Maria Ivanova");
    expect(within(own).getByText("You")).toBeVisible();
    expect(within(own).getByRole("combobox")).toBeDisabled();
    expect(within(own).queryByRole("button")).not.toBeInTheDocument();
  });

  it("is closed to agents, who don't see it in the menu either", async () => {
    renderApp("/admin/people", { signedInAs: elena });

    expect(await screen.findByText("Only admins can open this page")).toBeVisible();
    const menu = within(screen.getByRole("navigation", { name: "Main" }));
    expect(menu.queryByRole("link", { name: "People" })).not.toBeInTheDocument();
  });
});
