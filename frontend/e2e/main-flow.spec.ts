import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// The admin is created with `helpdesk create-admin` before the run; everyone else is made
// fresh here, with a run id in their emails so the test can run again on the same database.
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const run = Date.now().toString(36);

test.skip(!adminEmail || !adminPassword, "set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD");

async function addAgent(request: APIRequestContext, email: string, password: string) {
  const login = await request.post("/api/auth/token", {
    data: { email: adminEmail, password: adminPassword },
  });
  expect(login.ok()).toBe(true);
  const { access_token: token } = (await login.json()) as { access_token: string };
  const created = await request.post("/api/users", {
    headers: { Authorization: `Bearer ${token}` },
    data: { email, display_name: "Iliana Stoeva", role: "agent", password },
  });
  expect(created.status()).toBe(201);
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("a customer's ticket is picked up and answered by an agent", async ({ browser, request }) => {
  const agentEmail = `iliana.stoeva.${run}@northwind.test`;
  const agentPassword = "night-shift-2026";
  const subject = `Order confirmation emails land in spam (${run})`;
  await addAgent(request, agentEmail, agentPassword);

  // The customer signs up and opens a ticket.
  const customer = await (await browser.newContext()).newPage();
  await customer.goto("/sign-up");
  await customer.getByLabel("Your name").fill("Kalina Hristova");
  await customer.getByLabel("Email").fill(`kalina.hristova.${run}@initech.test`);
  await customer.getByLabel("Password").fill("lavender-field-31");
  await customer.getByRole("button", { name: "Create account" }).click();
  await expect(customer.getByRole("heading", { name: "Your tickets" })).toBeVisible();

  await customer.getByRole("link", { name: "New ticket" }).first().click();
  await customer.getByLabel("Subject").fill(subject);
  await customer
    .getByLabel("What happened?")
    .fill("Since Monday every order confirmation goes to spam in Gmail and Outlook.");
  await customer.getByLabel("Priority").selectOption("high");
  await customer.getByRole("button", { name: "Open ticket" }).click();
  await expect(customer.getByRole("heading", { name: subject })).toBeVisible();
  const ticketUrl = customer.url();

  // An agent finds it in the queue, takes it and replies.
  const agent = await (await browser.newContext()).newPage();
  await signIn(agent, agentEmail, agentPassword);
  await agent.getByLabel("Assignee").selectOption("unassigned");
  await agent.getByRole("link", { name: subject }).click();
  await agent.getByRole("button", { name: "Take it" }).click();
  await expect(agent.getByRole("combobox", { name: "Assignee" })).toHaveValue(/.+/);
  await agent.getByRole("combobox", { name: "Status" }).selectOption("in_progress");
  await agent.getByRole("radio", { name: "Internal note" }).check();
  await agent
    .getByRole("textbox", { name: "Internal note" })
    .fill("SPF record lost the new mail provider.");
  await agent.getByRole("button", { name: "Add note" }).click();
  await agent.getByRole("radio", { name: "Reply to customer" }).check();
  await agent
    .getByRole("textbox", { name: "Your reply" })
    .fill("Found it: a DNS change dropped our mail provider. Fixed, new emails arrive normally.");
  await agent.getByRole("button", { name: "Send reply" }).click();
  await expect(agent.getByText("Replied", { exact: true })).toBeVisible();

  // The customer sees the reply, but not the note.
  await customer.goto(ticketUrl);
  const conversation = customer.getByRole("region", { name: "Conversation" });
  await expect(conversation.getByText(/a DNS change dropped our mail provider/)).toBeVisible();
  await expect(conversation.getByText("Iliana Stoeva")).toBeVisible();
  await expect(conversation.getByText(/SPF record/)).toHaveCount(0);
  await expect(customer.getByText("In progress", { exact: true })).toBeVisible();
});
