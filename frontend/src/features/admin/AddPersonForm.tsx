import { useState, type SubmitEvent } from "react";

import type { Role } from "@/api/types";
import { useAddPerson } from "@/features/admin/api";
import styles from "@/features/admin/AddPersonForm.module.css";
import { accountErrorMessage } from "@/features/admin/errors";
import { roleNames, roles } from "@/features/admin/roles";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { SelectField } from "@/ui/SelectField";
import { TextField } from "@/ui/TextField";

interface AddPersonFormProps {
  onAdded: (name: string) => void;
  onCancel: () => void;
}

export function AddPersonForm({ onAdded, onCancel }: AddPersonFormProps) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("agent");
  const [password, setPassword] = useState("");
  const addPerson = useAddPerson();

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    addPerson.mutate(
      { display_name: displayName, email, role, password },
      {
        onSuccess: () => {
          onAdded(displayName);
        },
      },
    );
  }

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Add a person">
      {addPerson.error && <Notice tone="danger">{accountErrorMessage(addPerson.error)}</Notice>}
      <div className={styles.fields}>
        <TextField
          label="Name"
          required
          maxLength={100}
          value={displayName}
          onChange={(event) => {
            setDisplayName(event.target.value);
          }}
        />
        <TextField
          label="Email"
          type="email"
          required
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
          }}
        />
        <SelectField
          label="Role"
          value={role}
          onChange={(event) => {
            const chosen = roles.find((option) => option === event.target.value);
            if (chosen) {
              setRole(chosen);
            }
          }}
        >
          {roles.map((option) => (
            <option key={option} value={option}>
              {roleNames[option]}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Temporary password"
          type="text"
          autoComplete="off"
          required
          minLength={10}
          maxLength={128}
          hint="At least 10 characters. Pass it on privately; an admin can reset it later with the CLI."
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
      </div>
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={addPerson.isPending}>
          {addPerson.isPending ? "Adding…" : "Add person"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
