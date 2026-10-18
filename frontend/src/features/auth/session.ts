import type { Middleware } from "openapi-fetch";

export interface Session {
  accessToken: string;
  expiresAt: Date;
}

export type SessionEnd = "signed_out" | "expired";

export interface SessionState {
  session: Session | null;
  // Why the last session ended, so the sign-in page can say "your session expired".
  ended: SessionEnd | null;
}

const STORAGE_KEY = "helpdesk.session";

// Holds the access token outside React so the API middleware and the components agree on
// it. sessionStorage keeps it across reloads but not across tabs or browser restarts.
export class SessionStore {
  readonly #storage: Storage | null;
  readonly #listeners = new Set<() => void>();
  #state: SessionState;
  #expiryTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(storage: Storage | null) {
    this.#storage = storage;
    this.#state = { session: this.#restore(), ended: null };
    this.#scheduleExpiry();
  }

  get state(): SessionState {
    return this.#state;
  }

  get current(): Session | null {
    return this.#state.session;
  }

  start(accessToken: string, expiresAt: Date): void {
    const session = { accessToken, expiresAt };
    this.#write(JSON.stringify({ accessToken, expiresAt: expiresAt.toISOString() }));
    this.#update({ session, ended: null });
  }

  end(reason: SessionEnd): void {
    if (!this.#state.session) {
      return;
    }
    this.#write(null);
    this.#update({ session: null, ended: reason });
  }

  subscribe = (listener: () => void): (() => void) => {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  };

  #update(state: SessionState): void {
    this.#state = state;
    this.#scheduleExpiry();
    for (const listener of this.#listeners) {
      listener();
    }
  }

  #scheduleExpiry(): void {
    clearTimeout(this.#expiryTimer);
    const session = this.#state.session;
    if (session) {
      const remaining = session.expiresAt.getTime() - Date.now();
      this.#expiryTimer = setTimeout(() => {
        this.end("expired");
      }, remaining);
    }
  }

  #restore(): Session | null {
    const saved = this.#read();
    if (!saved) {
      return null;
    }
    try {
      const parsed: unknown = JSON.parse(saved);
      if (isStoredSession(parsed)) {
        const expiresAt = new Date(parsed.expiresAt);
        if (expiresAt.getTime() > Date.now()) {
          return { accessToken: parsed.accessToken, expiresAt };
        }
      }
    } catch {
      // A corrupt entry is treated like no session; the user signs in again.
    }
    this.#write(null);
    return null;
  }

  // Storage throws in some private modes and when site data is blocked; the session then
  // simply lasts until the page closes.
  #read(): string | null {
    try {
      return this.#storage?.getItem(STORAGE_KEY) ?? null;
    } catch {
      return null;
    }
  }

  #write(value: string | null): void {
    try {
      if (value === null) {
        this.#storage?.removeItem(STORAGE_KEY);
      } else {
        this.#storage?.setItem(STORAGE_KEY, value);
      }
    } catch {
      // See #read.
    }
  }
}

function isStoredSession(value: unknown): value is { accessToken: string; expiresAt: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "accessToken" in value &&
    "expiresAt" in value &&
    typeof value.accessToken === "string" &&
    typeof value.expiresAt === "string"
  );
}

export function sessionMiddleware(store: SessionStore): Middleware {
  return {
    onRequest({ request }) {
      const session = store.current;
      if (session) {
        request.headers.set("Authorization", `Bearer ${session.accessToken}`);
      }
      return request;
    },
    onResponse({ request, response }) {
      // A 401 for a request that carried a token: it expired early or the account was
      // deactivated. A 401 from the sign-in form itself is just a wrong password.
      if (response.status === 401 && request.headers.has("Authorization")) {
        store.end("expired");
      }
      return response;
    },
  };
}
