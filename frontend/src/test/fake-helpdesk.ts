import { http, HttpResponse, type HttpHandler } from "msw";

import type { components } from "@/api/schema";
import type { Comment, Person, Ticket, TicketStatus, User } from "@/api/types";
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
  readonly comments = new Map<string, Comment[]>();
  readonly #tokens = new Map<string, User>();
  readonly #idempotencyKeys = new Map<string, string>();
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
    this.comments.set(ticket.id, []);
    return ticket;
  }

  seedComment(ticket: Ticket, author: Account, body: string, internal = false): Comment {
    const comment: Comment = {
      id: crypto.randomUUID(),
      ticket_id: ticket.id,
      author: personFrom(author.user),
      body,
      visibility: internal ? "internal" : "public",
      created_at: new Date().toISOString(),
    };
    this.comments.get(ticket.id)?.push(comment);
    return comment;
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
        const priorities = query.getAll("priority");
        const assignee = query.get("assignee");
        const sort = query.get("sort") ?? "newest";
        const limit = Number(query.get("limit") ?? 25);
        const offset = Number(query.get("cursor") ?? 0);
        const matching = this.tickets
          .filter((ticket) => this.#canSee(user, ticket))
          .filter((ticket) => statuses.length === 0 || statuses.includes(ticket.status))
          .filter((ticket) => priorities.length === 0 || priorities.includes(ticket.priority))
          .filter((ticket) => {
            if (assignee === null || user.role === "customer") return true;
            if (assignee === "unassigned") return ticket.assignee === null;
            return ticket.assignee?.id === (assignee === "me" ? user.id : assignee);
          })
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

      http.post("/api/tickets", async ({ request }) => {
        const user = this.#authenticate(request);
        if (!user) {
          return refuse(401, "invalid_token", "token is invalid");
        }
        const body = (await request.json()) as Schemas["OpenTicketRequest"];
        const key = request.headers.get("Idempotency-Key");
        const earlier = key && this.#idempotencyKeys.get(`${user.id}:${key}`);
        const replay = earlier && this.tickets.find((ticket) => ticket.id === earlier);
        if (replay) {
          return HttpResponse.json(replay, { status: 201 });
        }
        for (const field of ["subject", "description"] as const) {
          if (!body[field].trim()) {
            return refuse(422, "invalid_value", `${field} must not be blank`);
          }
        }
        const account = this.accounts.find((candidate) => candidate.user.id === user.id);
        if (!account) {
          return refuse(401, "invalid_token", "token is invalid");
        }
        const ticket = this.seedTicket({
          subject: body.subject,
          description: body.description,
          priority: body.priority ?? "normal",
          requester: account,
        });
        if (key) {
          this.#idempotencyKeys.set(`${user.id}:${key}`, ticket.id);
        }
        return HttpResponse.json(ticket, { status: 201 });
      }),

      http.get("/api/tickets/:ticketId", ({ request, params }) => {
        const found = this.#visibleTicket(request, params.ticketId);
        return found instanceof Response ? found : HttpResponse.json(found.ticket);
      }),

      http.get("/api/tickets/:ticketId/comments", ({ request, params }) => {
        const found = this.#visibleTicket(request, params.ticketId);
        if (found instanceof Response) {
          return found;
        }
        const thread = this.comments.get(found.ticket.id) ?? [];
        const staff = found.user.role !== "customer";
        return HttpResponse.json(
          thread.filter((comment) => staff || comment.visibility === "public"),
        );
      }),

      http.post("/api/tickets/:ticketId/comments", async ({ request, params }) => {
        const found = this.#visibleTicket(request, params.ticketId);
        if (found instanceof Response) {
          return found;
        }
        const { ticket, user } = found;
        const body = (await request.json()) as Schemas["AddCommentRequest"];
        if (ticket.status === "closed") {
          return refuse(409, "ticket_closed", `ticket ${ticket.id} is closed`);
        }
        const internal = body.visibility === "internal";
        if (internal && user.role === "customer") {
          return refuse(403, "internal_note_not_allowed", "only staff can write internal notes");
        }
        const author = this.accounts.find((account) => account.user.id === user.id);
        if (!author) {
          return refuse(401, "invalid_token", "token is invalid");
        }
        const comment = this.seedComment(ticket, author, body.body, internal);
        ticket.updated_at = comment.created_at;
        if (user.id === ticket.requester.id) {
          if (ticket.status === "waiting_on_customer") ticket.status = "in_progress";
          if (ticket.status === "resolved") ticket.status = "open";
        } else if (!internal && ticket.first_responded_at === null) {
          ticket.first_responded_at = comment.created_at;
        }
        return HttpResponse.json(comment, { status: 201 });
      }),
    ];
  }

  #visibleTicket(
    request: Request,
    ticketId: string | readonly string[] | undefined,
  ): { ticket: Ticket; user: User } | Response {
    const user = this.#authenticate(request);
    if (!user) {
      return refuse(401, "invalid_token", "token is invalid");
    }
    const ticket = this.tickets.find((candidate) => candidate.id === ticketId);
    if (!ticket || !this.#canSee(user, ticket)) {
      return refuse(404, "ticket_not_found", `ticket ${String(ticketId)} not found`);
    }
    return { ticket, user };
  }

  #canSee(user: User, ticket: Ticket): boolean {
    return user.role !== "customer" || ticket.requester.id === user.id;
  }

  #authenticate(request: Request): User | undefined {
    const token = request.headers.get("Authorization")?.replace(/^Bearer /, "");
    return token ? this.#tokens.get(token) : undefined;
  }
}
