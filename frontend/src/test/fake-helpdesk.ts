import { http, HttpResponse, type HttpHandler } from "msw";

import type { components } from "@/api/schema";
import type { User } from "@/api/types";
import { elena, maria, petar, type Account } from "@/test/fixtures";

type Schemas = components["schemas"];

const TOKEN_LIFETIME_MS = 15 * 60 * 1000;

function refuse(status: number, code: string, detail: string) {
  return HttpResponse.json({ detail, code } satisfies Schemas["ErrorResponse"], { status });
}

// Just enough of the backend for the frontend's tests: real status codes and error codes,
// accounts kept in memory, tokens that can be revoked to simulate an expired session.
export class FakeHelpdesk {
  readonly accounts: Account[];
  readonly #tokens = new Map<string, User>();
  #failProfileRequests = 0;

  constructor(accounts: Account[] = [petar, elena, maria]) {
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

  #authenticate(request: Request): User | undefined {
    const token = request.headers.get("Authorization")?.replace(/^Bearer /, "");
    return token ? this.#tokens.get(token) : undefined;
  }
}
