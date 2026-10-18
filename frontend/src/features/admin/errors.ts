import { ApiError } from "@/api/client";

export function accountErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "email_taken":
        return "An account with this email already exists.";
      case "own_account":
        return "You can't change your own role or lock yourself out. Ask another admin.";
      case "concurrent_update":
        return "Someone else changed this account at the same moment. Check it and try again.";
      case "invalid_value": {
        const text = error.message;
        return `${text.charAt(0).toUpperCase()}${text.slice(1)}${text.endsWith(".") ? "" : "."}`;
      }
    }
  }
  return "Couldn't reach the helpdesk. Try again in a moment.";
}
