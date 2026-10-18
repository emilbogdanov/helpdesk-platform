import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, unwrap } from "@/api/client";
import { SessionStore, sessionMiddleware } from "@/features/auth/session";

const IN_15_MINUTES = () => new Date(Date.now() + 15 * 60 * 1000);

afterEach(() => {
  vi.useRealTimers();
});

describe("SessionStore", () => {
  it("survives a reload until the token expires", () => {
    const expiresAt = IN_15_MINUTES();
    new SessionStore(sessionStorage).start("token-petar", expiresAt);

    const afterReload = new SessionStore(sessionStorage);

    expect(afterReload.current).toEqual({ accessToken: "token-petar", expiresAt });
  });

  it("drops a stored session whose token has already expired", () => {
    sessionStorage.setItem(
      "helpdesk.session",
      JSON.stringify({ accessToken: "token-petar", expiresAt: "2026-10-18T08:00:00Z" }),
    );

    expect(new SessionStore(sessionStorage).current).toBeNull();
    expect(sessionStorage.getItem("helpdesk.session")).toBeNull();
  });

  it("treats a corrupt stored session as signed out", () => {
    sessionStorage.setItem("helpdesk.session", "{not json");

    expect(new SessionStore(sessionStorage).current).toBeNull();
  });

  it("ends the session the moment the token runs out", () => {
    vi.useFakeTimers();
    const store = new SessionStore(null);
    store.start("token-petar", IN_15_MINUTES());

    vi.advanceTimersByTime(15 * 60 * 1000 - 1);
    expect(store.current).not.toBeNull();
    vi.advanceTimersByTime(1);

    expect(store.state).toEqual({ session: null, ended: "expired" });
  });

  it("tells subscribers about every change and why the session ended", () => {
    const store = new SessionStore(null);
    const seen: (string | null)[] = [];
    store.subscribe(() => seen.push(store.state.ended ?? store.current?.accessToken ?? null));

    store.start("token-elena", IN_15_MINUTES());
    store.end("signed_out");
    store.end("signed_out");

    expect(seen).toEqual(["token-elena", "signed_out"]);
  });

  it("keeps working when the browser refuses storage", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("blocked", "SecurityError");
      },
      setItem: () => {
        throw new DOMException("blocked", "SecurityError");
      },
      removeItem: () => {
        throw new DOMException("blocked", "SecurityError");
      },
    } as unknown as Storage;

    const store = new SessionStore(blocked);
    store.start("token-maria", IN_15_MINUTES());

    expect(store.current?.accessToken).toBe("token-maria");
  });
});

describe("sessionMiddleware", () => {
  function clientWith(store: SessionStore, status: number) {
    const sent: Request[] = [];
    const client = createApiClient({
      baseUrl: "http://helpdesk.test/api",
      fetch: (request) => {
        sent.push(request);
        return Promise.resolve(
          Response.json({ detail: "rejected", code: "invalid_token" }, { status }),
        );
      },
    });
    client.use(sessionMiddleware(store));
    return { client, sent };
  }

  it("sends the access token with every request", async () => {
    const store = new SessionStore(null);
    store.start("token-elena", IN_15_MINUTES());
    const { client, sent } = clientWith(store, 200);

    await client.GET("/users/me");

    expect(sent[0]?.headers.get("Authorization")).toBe("Bearer token-elena");
  });

  it("ends the session when the API rejects the token", async () => {
    const store = new SessionStore(null);
    store.start("token-elena", IN_15_MINUTES());
    const { client } = clientWith(store, 401);

    await expect(unwrap(client.GET("/users/me"))).rejects.toThrow("rejected");

    expect(store.state.ended).toBe("expired");
  });

  it("leaves the session alone when a sign-in attempt is refused", async () => {
    const store = new SessionStore(null);
    const subscriber = vi.fn();
    store.subscribe(subscriber);
    const { client } = clientWith(store, 401);

    await client.POST("/auth/token", {
      body: { email: "petar.georgiev@acme.test", password: "x" },
    });

    expect(subscriber).not.toHaveBeenCalled();
  });
});
