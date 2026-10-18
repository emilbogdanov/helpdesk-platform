import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { petar } from "@/test/fixtures";
import { renderApp } from "@/test/render-app";

describe("signing up", () => {
  it("creates a customer account and signs straight in", async () => {
    const { user } = renderApp("/sign-up");

    await user.type(screen.getByLabelText("Your name"), "Ivo Stoyanov");
    await user.type(screen.getByLabelText("Email"), "ivo.stoyanov@globex.test");
    await user.type(screen.getByLabelText("Password"), "granite-meadow-88");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByText("ivo.stoyanov@globex.test")).toBeInTheDocument();
    expect(screen.getByText(/^Customer: you can open tickets/)).toBeInTheDocument();
  });

  it("points to sign-in when the email already has an account", async () => {
    const { user } = renderApp("/sign-up");

    await user.type(screen.getByLabelText("Your name"), "Petar Georgiev");
    await user.type(screen.getByLabelText("Email"), petar.user.email);
    await user.type(screen.getByLabelText("Password"), "another-password-9");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    const email = screen.getByLabelText("Email");
    expect(await screen.findByText("An account with this email already exists.")).toBeVisible();
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("link", { name: "Sign in instead" })).toHaveAttribute(
      "href",
      "/sign-in",
    );

    await user.type(email, "x");
    expect(email).not.toHaveAttribute("aria-invalid");
  });

  it("passes on the API's reason when it rejects a value", async () => {
    const { user } = renderApp("/sign-up");

    await user.type(screen.getByLabelText("Your name"), "   ");
    await user.type(screen.getByLabelText("Email"), "ivo.stoyanov@globex.test");
    await user.type(screen.getByLabelText("Password"), "granite-meadow-88");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Display name must not be blank.");
  });
});
