import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router";

import type { Priority } from "@/api/types";
import { useOpenTicket } from "@/features/tickets/api";
import { submitErrorMessage } from "@/features/tickets/errors";
import { firstResponseTargets, priorities, priorityLabels } from "@/features/tickets/labels";
import styles from "@/features/tickets/NewTicketPage.module.css";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { SelectField } from "@/ui/SelectField";
import { TextArea } from "@/ui/TextArea";
import { TextField } from "@/ui/TextField";

export function NewTicketPage() {
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("normal");
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const openTicket = useOpenTicket(idempotencyKey);
  const navigate = useNavigate();

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    openTicket.mutate(
      { subject, description, priority },
      {
        onSuccess: (ticket) => {
          void navigate(`/tickets/${ticket.id}`, { replace: true });
        },
      },
    );
  }

  return (
    <section className={styles.page} aria-labelledby="new-ticket-heading">
      <h1 id="new-ticket-heading" className={styles.heading}>
        New ticket
      </h1>
      <form className={styles.form} onSubmit={submit}>
        {openTicket.error && <Notice tone="danger">{submitErrorMessage(openTicket.error)}</Notice>}
        <TextField
          label="Subject"
          name="subject"
          required
          maxLength={200}
          hint="One line that tells support what's wrong, e.g. “Invoice PDF shows last month's VAT rate”."
          value={subject}
          onChange={(event) => {
            setSubject(event.target.value);
          }}
        />
        <TextArea
          label="What happened?"
          name="description"
          required
          maxLength={10_000}
          rows={8}
          hint="What you did, what you expected and what you saw instead. Order numbers and exact error messages help most."
          value={description}
          onChange={(event) => {
            setDescription(event.target.value);
          }}
        />
        <SelectField
          label="Priority"
          name="priority"
          value={priority}
          hint={`Support aims to reply ${firstResponseTargets[priority]}.`}
          onChange={(event) => {
            const chosen = priorities.find((option) => option === event.target.value);
            if (chosen) {
              setPriority(chosen);
            }
          }}
        >
          {priorities.map((option) => (
            <option key={option} value={option}>
              {priorityLabels[option]}
            </option>
          ))}
        </SelectField>
        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={openTicket.isPending}>
            {openTicket.isPending ? "Opening ticket…" : "Open ticket"}
          </Button>
          <Link to="/tickets">Cancel</Link>
        </div>
      </form>
    </section>
  );
}
