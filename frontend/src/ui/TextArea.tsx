import { useId, type ComponentProps, type ReactNode } from "react";

import styles from "@/ui/TextField.module.css";

interface TextAreaProps extends Omit<ComponentProps<"textarea">, "id"> {
  label: string;
  hint?: string;
  error?: ReactNode;
}

export function TextArea({ label, hint, error, ...textarea }: TextAreaProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(" ");

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <textarea
        id={id}
        className={styles.textarea}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...textarea}
      />
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
