import { ApiError } from "@/api/client";

const UNAVAILABLE = "Couldn't reach the helpdesk. Check your connection and try again.";

export function signInErrorMessage(error: Error): string {
  // Deactivated accounts get the same answer from the API, on purpose.
  if (error instanceof ApiError && error.code === "invalid_credentials") {
    return "That email and password don't match an active account.";
  }
  return UNAVAILABLE;
}

export interface SignUpProblem {
  field: "email" | null;
  message: string;
}

export function signUpProblem(error: Error): SignUpProblem {
  if (error instanceof ApiError) {
    if (error.code === "email_taken") {
      return { field: "email", message: "An account with this email already exists." };
    }
    if (error.code === "invalid_value") {
      // The API's wording is already specific ("password must be 10 to 128 characters").
      return { field: null, message: sentence(error.message) };
    }
  }
  return { field: null, message: UNAVAILABLE };
}

function sentence(text: string): string {
  const trimmed = text.trim();
  return `${trimmed.charAt(0).toUpperCase()}${trimmed.slice(1)}${trimmed.endsWith(".") ? "" : "."}`;
}
