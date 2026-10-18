import type { ComponentProps } from "react";

import styles from "@/ui/Button.module.css";
import { classNames } from "@/ui/class-names";

interface ButtonProps extends ComponentProps<"button"> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "sm";
}

export function Button({
  variant = "secondary",
  size = "md",
  type = "button",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classNames(styles.button, styles[variant], styles[size], className)}
      {...props}
    />
  );
}
