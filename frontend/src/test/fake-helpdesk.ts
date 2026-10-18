import { http, HttpResponse, type HttpHandler } from "msw";

import type { components } from "@/api/schema";
import type { Person, Ticket, TicketStatus, User } from "@/api/types";
import { elena, maria, nadia, petar, type Account } from "@/test/fixtures";

type Schemas = components["schemas"];

const TOKEN_LIFETIME_MS = 15 * 60 * 1000;

function refuse(status: number, code: string, detail: string) {
  return HttpResponse.json({ detail, code } satisfies Schemas["ErrorResponse"], { status });
}

function personFrom(user: User): Person {
  return { id: user.id, display_name: user.display_name, role: user.role };
}

export interface SeededTicket {
  subject: string;
  requester: Account;
  status?: TicketStatus;
  priority?: Ticket["priority"];
  assignee?: Account;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Just enough of the backend for the frontend's tests: real status codes and error codes,
// accounts and tickets kept in memory, and tokens that can be revoked to simulate an expired
// session. Ticket rules follow the backend's domain where the UI depends on them.
export class FakeHelpdesk {
  readonly accounts: Account[];
  readonly tickets: Ticket[] = [];
  readonly #tokens = new Map<string, User>();
  #failProfileRequests = 0;

  constructor(accounts: Account[] = [petar, nadia, elena, maria]) {
    this.accounts = accounts.map((account) => ({ ...account, user: { ...account.user } }));
  }

  issueToken(user: User): string {
    const token = `token-${user.id}-${this.#tokens.size + 1}`;
    this.#tokens.set(token, user);
    return token;
  }

  revokeAllTokens(): void {
    this.#tokens.clear();
  }

  failNextProfileRequests(count: number): void {
    this.#failProfileRequests = count;
  }

  seedTicket(seed: SeededTicket): Ticket {
    const createdAt = seed.createdAt ?? new Date().toISOString();
    const ticket: Ticket = {
      id: crypto.randomUUID(),
      requester: personFrom(seed.requester.user),
      subject: seed.subject,
      description: seed.description ?? "Details to follow.",
      priority: seed.priority ?? "normal",
      status: seed.status ?? "open",
      assignee: seed.assignee ? personFrom(seed.assignee.user) : null,
      created_at: createdAt,
      updated_at: seed.updatedAt ?? createdAt,
      resolved_at: null,
      closed_at: null,
      first_responded_at: null,
      sla_breached_at: null,
    };
    this.tickets.push(ticket);
    return ticket;
  }

  handlers(): HttpHandler[] {
    return [
      http.post("/api/auth/token", async ({ request }) => {
        const body = (await request.json()) as Schemas["TokenRequest"];
        const account = this.accounts.find(
          ({ user, password }) =>
            user.email === body.email.trim().toLowerCase() &&
            password === body.password &&
            user.is_active,
        );
        if (!account) {
          return refuse(401, "invalid_credentials", "email or password is incorrect");
        }
        return HttpResponse.json({
          access_token: this.issueToken(account.user),
          token_type: "bearer",
          expires_at: new Date(Date.now() + TOKEN_LIFETIME_MS).toISOString(),
        } satisfies Schemas["TokenResponse"]);
      }),

      http.post("/api/auth/sign-up", async ({ request }) => {
        const body = (await request.json()) as Schemas["SignUpRequest"];
        const email = body.email.trim().toLowerCase();
        if (!body.display_name.trim()) {
          return refuse(422, "invalid_value", "display name must not be blank");
        }
        if (this.accounts.some(({ user }) => user.email === email)) {
          return refuse(409, "email_taken", `an account already uses ${email}`);
        }
        const user: User = {
          id: crypto.randomUUID(),
          email,
          display_name: body.display_name,
          role: "customer",
          is_active: true,
          created_at: new Date().toISOString(),
        };
        this.accounts.push({ user, password: body.password });
        return HttpResponse.json(user, { status: 201 });
      }),

      ...this.#ticketHandlers(),

      http.get("/api/users/me", ({ request }) => {
        if (this.#failProfileRequests > 0) {
          this.#failProfileRequests -= 1;
          return new HttpResponse("upstream connect error", { status: 503 });
        }
        const user = this.#authenticate(request);
        return user ? HttpResponse.json(user) : refuse(401, "invalid_token", "token is invalid");
      }),
    ];
  }

  #ticketHandlers(): HttpHandler[] {
    return [
      http.get("/api/tickets", ({ request }) => {
        const user = this.#authenticate(request);
        if (!user) {
          return refuse(401, "invalid_token", "token is invalid");
        }
        const query = new URL(request.url).searchParams;
        const statuses = query.getAll("status");
        const sort = query.get("sort") ?? "newest";
        const limit = Number(query.get("limit") ?? 25);
        const offset = Number(query.get("cursor") ?? 0);
        const matching = this.tickets
          .filter((ticket) => this.#canSee(user, ticket))
          .filter((ticket) => statuses.length === 0 || statuses.includes(ticket.status))
          .sort((a, b) => {
            const key = sort === "recently_updated" ? "updated_at" : "created_at";
            const order = a[key].localeCompare(b[key]);
            return sort === "oldest" ? order : -order;
          });
        const items = matching.slice(offset, offset + limit);
        const hasMore = offset + limit < matching.length;
        return HttpResponse.json({
          items,
          next_cursor: hasMore ? String(offset + limit) : null,
        } satisfies Schemas["TicketListResponse"]);
      }),
    ];
  }

  #canSee(user: User, ticket: Ticket): boolean {
    return user.role !== "customer" || ticket.requester.id === user.id;
  }

  #authenticate(request: Request): User | undefined {
    const token = request.headers.get("Authorization")?.replace(/^Bearer /, "");
    return token ? this.#tokens.get(token) : undefined;
  }
}
