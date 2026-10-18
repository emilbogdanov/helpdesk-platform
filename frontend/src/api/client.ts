import createClient, { type ClientOptions } from "openapi-fetch";

import type { components, paths } from "@/api/schema";

type ErrorBody = components["schemas"]["ErrorResponse"];

export class ApiError extends Error {
  override readonly name = "ApiError";
  readonly status: number;
  // The API's machine-readable reason, e.g. "invalid_status_transition"; branch on this,
  // never on the message.
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function createApiClient(options: ClientOptions = {}) {
  return createClient<paths>({ baseUrl: "/api", ...options });
}

export const api = createApiClient();

interface Outcome<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

// openapi-fetch resolves with either data or error; TanStack Query wants a promise that
// rejects on failure, so every call goes through here.
export async function unwrap<Data>(request: Promise<Outcome<Data>>): Promise<Data> {
  const { data, error, response } = await request;
  if (!response.ok || data === undefined) {
    throw toApiError(response, error);
  }
  return data;
}

function toApiError(response: Response, body: unknown): ApiError {
  if (isErrorBody(body)) {
    return new ApiError(response.status, body.code, body.detail);
  }
  // Not an answer from the API itself: a proxy's error page, a gateway timeout, no body.
  const reason = `${response.status} ${response.statusText}`.trim();
  return new ApiError(response.status, "unexpected_response", reason);
}

function isErrorBody(body: unknown): body is ErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    "code" in body &&
    typeof body.detail === "string" &&
    typeof body.code === "string"
  );
}
