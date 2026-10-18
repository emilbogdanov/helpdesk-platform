import { useState, type SubmitEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { useSignIn } from "@/features/auth/api";
import styles from "@/features/auth/AuthLayout.module.css";
import { signInErrorMessage } from "@/features/auth/errors";
import { useSessionState } from "@/features/auth/session-context";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { TextField } from "@/ui/TextField";

export function SignInPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const signIn = useSignIn();
  const { ended } = useSessionState();
  const [params] = useSearchParams();

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    signIn.mutate({ email, password });
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h1 className={styles.heading}>Sign in</h1>
      {ended === "expired" && !signIn.error && (
        <Notice tone="info">
          Your session expired. Sign in again to pick up where you left off.
        </Notice>
      )}
      {signIn.error && <Notice tone="danger">{signInErrorMessage(signIn.error)}</Notice>}
      <TextField
        label="Email"
        type="email"
        name="email"
        autoComplete="username"
        required
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
        }}
      />
      <TextField
        label="Password"
        type="password"
        name="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(event) => {
          setPassword(event.target.value);
        }}
      />
      <Button type="submit" variant="primary" disabled={signIn.isPending}>
        {signIn.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <p className={styles.footer}>
        New here?{" "}
        <Link to={{ pathname: "/sign-up", search: params.toString() }}>Create an account</Link>
      </p>
    </form>
  );
}
