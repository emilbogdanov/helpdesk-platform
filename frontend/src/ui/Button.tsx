import type { ComponentProps } from "react";
import { Link } from "react-router";

import styles from "@/ui/Button.module.css";
import { classNames } from "@/ui/class-names";

interface Appearance {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "sm";
}

function buttonClassName({ variant = "secondary", size = "md" }: Appearance, extra?: string) {
  return classNames(styles.button, styles[variant], styles[size], extra);
}

export function Button({
  variant,
  size,
  type = "button",
  className,
  ...props
}: ComponentProps<"button"> & Appearance) {
  return (
    <button type={type} className={buttonClassName({ variant, size }, className)} {...props} />
  );
}

// Navigation that looks like a button, e.g. "New ticket": still a link to assistive tech.
export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: ComponentProps<typeof Link> & Appearance) {
  return <Link className={buttonClassName({ variant, size }, className)} {...props} />;
}
