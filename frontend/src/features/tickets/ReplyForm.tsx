import { useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import type { Ticket } from "@/api/types";
import { useAddComment } from "@/features/tickets/api";
import { submitErrorMessage } from "@/features/tickets/errors";
import type { Audience } from "@/features/tickets/labels";
import styles from "@/features/tickets/ReplyForm.module.css";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { TextArea } from "@/ui/TextArea";

export function ReplyForm({ ticket, audience }: { ticket: Ticket; audience: Audience }) {
  const [body, setBody] = useState("");
  const addComment = useAddComment(ticket.id);

  if (ticket.status === "closed") {
    return (
      <p className={styles.closed}>
        This ticket is closed and can't take new replies.{" "}
        {audience === "requester" && <Link to="/tickets/new">Open a new ticket</Link>}
      </p>
    );
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    addComment.mutate(
      { body },
      {
        onSuccess: () => {
          setBody("");
        },
      },
    );
  }

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Reply">
      {audience === "requester" && <RequesterHint status={ticket.status} />}
      {addComment.error && <Notice tone="danger">{submitErrorMessage(addComment.error)}</Notice>}
      <TextArea
        label="Your reply"
        name="body"
        required
        maxLength={10_000}
        rows={5}
        value={body}
        onChange={(event) => {
          setBody(event.target.value);
        }}
      />
      <div>
        <Button type="submit" variant="primary" disabled={addComment.isPending || !body.trim()}>
          {addComment.isPending ? "Sending…" : "Send reply"}
        </Button>
      </div>
    </form>
  );
}

function RequesterHint({ status }: { status: Ticket["status"] }) {
  if (status === "waiting_on_customer") {
    return <Notice tone="info">Support is waiting for your reply before they can continue.</Notice>;
  }
  if (status === "resolved") {
    return (
      <Notice tone="info">
        Support marked this resolved. If it isn't fixed, reply and the ticket reopens.
      </Notice>
    );
  }
  return null;
}
