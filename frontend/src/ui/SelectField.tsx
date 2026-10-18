import { useId, type ComponentProps } from "react";

import styles from "@/ui/TextField.module.css";

interface SelectFieldProps extends Omit<ComponentProps<"select">, "id"> {
  label: string;
  hint?: string;
}

export function SelectField({ label, hint, children, ...select }: SelectFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <select
        id={id}
        className={styles.select}
        aria-describedby={hint ? hintId : undefined}
        {...select}
      >
        {children}
      </select>
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
    </div>
  );
}
