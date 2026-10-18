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

// The backend's transition table (domain/tickets/status.py), copied rather than imported from
// the app so a mistake in the app's own copy can't hide here as well.
const TRANSITIONS: Record<TicketStatus, readonly TicketStatus[]> = {
  open: ["in_progress", "resolved", "closed"],
  in_progress: ["open", "waiting_on_customer", "resolved"],
  waiting_on_customer: ["in_progress", "resolved"],
  resolved: ["open", "closed"],
  closed: [],
};
const WORKED: readonly TicketStatus[] = ["in_progress", "waiting_on_customer"];

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
  // Token -> user id. Like the backend, every request reloads the account, so role changes
  // and deactivations apply to tokens already handed out.
  readonly #tokens = new Map<string, string>();
  readonly #idempotencyKeys = new Map<string, string>();
  #failProfileRequests = 0;
  #conflictOnNextChange = false;

  constructor(accounts: Account[] = [petar, nadia, elena, maria]) {
    this.accounts = accounts.map((account) => ({ ...account, user: { ...account.user } }));
  }

  issueToken(user: User): string {
    const token = `token-${user.id}-${this.#tokens.size + 1}`;
    this.#tokens.set(token, user.id);
    return token;
  }

  revokeAllTokens(): void {
    this.#tokens.clear();
  }

  failNextProfileRequests(count: number): void {
    this.#failProfileRequests = count;
  }

  // As if another agent saved the ticket first: the next change gets a 409.
  conflictOnNextChange(): void {
    this.#conflictOnNextChange = true;
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
      ...this.#adminHandlers(),

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

      http.put("/api/tickets/:ticketId/status", async ({ request, params }) => {
        const body = (await request.json()) as Schemas["StatusChangeRequest"];
        return this.#change(request, params.ticketId, (ticket) => {
          if (!TRANSITIONS[ticket.status].includes(body.status)) {
            return refuse(
              409,
              "invalid_status_transition",
              `cannot move a ticket from ${ticket.status} to ${body.status}`,
            );
          }
          if (WORKED.includes(body.status) && ticket.assignee === null) {
            return refuse(409, "assignee_required", "assign the ticket first");
          }
          ticket.status = body.status;
          return undefined;
        });
      }),

      http.put("/api/tickets/:ticketId/priority", async ({ request, params }) => {
        const body = (await request.json()) as Schemas["PriorityChangeRequest"];
        return this.#change(request, params.ticketId, (ticket) => {
          ticket.priority = body.priority;
          return undefined;
        });
      }),

      http.put("/api/tickets/:ticketId/assignee", async ({ request, params }) => {
        const body = (await request.json()) as Schemas["AssigneeChangeRequest"];
        return this.#change(request, params.ticketId, (ticket) => {
          const assignee = this.#staff().find((person) => person.id === body.assignee_id);
          if (!assignee) {
            return refuse(422, "invalid_assignee", "only active staff can take tickets");
          }
          ticket.assignee = assignee;
          return undefined;
        });
      }),

      http.delete("/api/tickets/:ticketId/assignee", ({ request, params }) =>
        this.#change(request, params.ticketId, (ticket) => {
          if (WORKED.includes(ticket.status)) {
            return refuse(409, "assignee_required", `a ticket ${ticket.status} needs an assignee`);
          }
          ticket.assignee = null;
          return undefined;
        }),
      ),

      http.post("/api/tickets/:ticketId/take", ({ request, params }) =>
        this.#change(request, params.ticketId, (ticket, user) => {
          ticket.assignee = personFrom(user);
          return undefined;
        }),
      ),

      http.get("/api/users/staff", ({ request }) => {
        const user = this.#authenticate(request);
        if (!user) {
          return refuse(401, "invalid_token", "token is invalid");
        }
        if (user.role === "customer") {
          return refuse(403, "staff_only", "only agents and admins can see who is on the team");
        }
        return HttpResponse.json(this.#staff());
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

  #adminHandlers(): HttpHandler[] {
    return [
      http.get("/api/users", ({ request }) => {
        const admin = this.#admin(request);
        if (admin instanceof Response) {
          return admin;
        }
        const query = new URL(request.url).searchParams;
        const needle = (query.get("q") ?? "").trim().toLowerCase();
        const role = query.get("role");
        const status = query.get("status");
        const limit = Number(query.get("limit") ?? 50);
        const offset = Number(query.get("cursor") ?? 0);
        const matching = this.accounts
          .map(({ user }) => user)
          .filter((user) => role === null || user.role === role)
          .filter((user) => status === null || user.is_active === (status === "active"))
          .filter(
            (user) =>
              user.display_name.toLowerCase().includes(needle) || user.email.includes(needle),
          )
          .sort((a, b) => a.display_name.localeCompare(b.display_name));
        const hasMore = offset + limit < matching.length;
        return HttpResponse.json({
          items: matching.slice(offset, offset + limit),
          next_cursor: hasMore ? String(offset + limit) : null,
        } satisfies Schemas["UserListResponse"]);
      }),

      http.post("/api/users", async ({ request }) => {
        const admin = this.#admin(request);
        if (admin instanceof Response) {
          return admin;
        }
        const body = (await request.json()) as Schemas["CreateUserRequest"];
        const email = body.email.trim().toLowerCase();
        if (body.password.length < 10) {
          return refuse(422, "invalid_value", "password must be 10 to 128 characters");
        }
        if (this.accounts.some(({ user }) => user.email === email)) {
          return refuse(409, "email_taken", `an account already uses ${email}`);
        }
        const user: User = {
          id: crypto.randomUUID(),
          email,
          display_name: body.display_name,
          role: body.role,
          is_active: true,
          created_at: new Date().toISOString(),
        };
        this.accounts.push({ user, password: body.password });
        return HttpResponse.json(user, { status: 201 });
      }),

      http.put("/api/users/:userId/role", async ({ request, params }) => {
        const body = (await request.json()) as Schemas["RoleChangeRequest"];
        return this.#manage(request, params.userId, (user) => {
          user.role = body.role;
        });
      }),

      http.post("/api/users/:userId/deactivate", ({ request, params }) =>
        this.#manage(request, params.userId, (user) => {
          user.is_active = false;
        }),
      ),

      http.post("/api/users/:userId/reactivate", ({ request, params }) =>
        this.#manage(request, params.userId, (user) => {
          user.is_active = true;
        }),
      ),
    ];
  }

  #manage(
    request: Request,
    userId: string | readonly string[] | undefined,
    change: (user: User) => void,
  ): Response {
    const admin = this.#admin(request);
    if (admin instanceof Response) {
      return admin;
    }
    const account = this.#account(userId);
    if (!account) {
      return refuse(404, "user_not_found", `user ${String(userId)} not found`);
    }
    if (account.user.id === admin.id) {
      return refuse(403, "own_account", "admins can't change their own account");
    }
    change(account.user);
    return HttpResponse.json(account.user);
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

  #change(
    request: Request,
    ticketId: string | readonly string[] | undefined,
    apply: (ticket: Ticket, user: User) => Response | undefined,
  ): Response {
    const found = this.#visibleTicket(request, ticketId);
    if (found instanceof Response) {
      return found;
    }
    const { ticket, user } = found;
    if (user.role === "customer") {
      return refuse(403, "staff_only", "only agents and admins can change tickets");
    }
    if (this.#conflictOnNextChange) {
      this.#conflictOnNextChange = false;
      return refuse(409, "concurrent_update", "the ticket was changed by someone else");
    }
    if (ticket.status === "closed") {
      return refuse(409, "ticket_closed", `ticket ${ticket.id} is closed`);
    }
    const refused = apply(ticket, user);
    if (refused) {
      return refused;
    }
    ticket.updated_at = new Date().toISOString();
    return HttpResponse.json(ticket);
  }

  #staff(): Person[] {
    return this.accounts
      .map(({ user }) => user)
      .filter((user) => user.role !== "customer" && user.is_active)
      .sort((a, b) => a.display_name.localeCompare(b.display_name))
      .map(personFrom);
  }

  #canSee(user: User, ticket: Ticket): boolean {
    return user.role !== "customer" || ticket.requester.id === user.id;
  }

  #authenticate(request: Request): User | undefined {
    const token = request.headers.get("Authorization")?.replace(/^Bearer /, "");
    const userId = token ? this.#tokens.get(token) : undefined;
    const user = this.accounts.find((account) => account.user.id === userId)?.user;
    return user?.is_active ? user : undefined;
  }

  #admin(request: Request): User | Response {
    const user = this.#authenticate(request);
    if (!user) {
      return refuse(401, "invalid_token", "token is invalid");
    }
    if (user.role !== "admin") {
      return refuse(403, "admin_only", "only admins can manage accounts");
    }
    return user;
  }

  #account(userId: string | readonly string[] | undefined): Account | undefined {
    return this.accounts.find((account) => account.user.id === userId);
  }
}
