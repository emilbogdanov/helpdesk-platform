import { ApiError } from "@/api/client";

const UNAVAILABLE = "Couldn't reach the helpdesk. Your text is still here; try again in a moment.";

// For forms: the API's own wording for a rejected value, otherwise a retry hint.
export function submitErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "invalid_value":
        return capitalise(error.message);
      case "ticket_closed":
        return "This ticket was closed in the meantime, so it can't take more replies.";
      case "ticket_not_found":
        return "This ticket no longer exists or you can't see it any more.";
    }
  }
  return UNAVAILABLE;
}

function capitalise(text: string): string {
  const sentence = text.charAt(0).toUpperCase() + text.slice(1);
  return sentence.endsWith(".") ? sentence : `${sentence}.`;
}
