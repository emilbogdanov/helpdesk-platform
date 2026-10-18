import { useState, type SubmitEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { useSignUp } from "@/features/auth/api";
import styles from "@/features/auth/AuthLayout.module.css";
import { signUpProblem } from "@/features/auth/errors";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { TextField } from "@/ui/TextField";

const PASSWORD_MIN_LENGTH = 10;

export function SignUpPage() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const signUp = useSignUp();
  const [params] = useSearchParams();
  const signInLink = { pathname: "/sign-in", search: params.toString() };
  const problem = signUp.error ? signUpProblem(signUp.error) : null;

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    signUp.mutate({ display_name: displayName, email, password });
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <h1 className={styles.heading}>Create an account</h1>
      {problem && !problem.field && <Notice tone="danger">{problem.message}</Notice>}
      <TextField
        label="Your name"
        name="display_name"
        autoComplete="name"
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
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
          // A "taken" error is about the old address; don't leave it under a new one.
          if (problem?.field === "email") {
            signUp.reset();
          }
        }}
        error={
          problem?.field === "email" && (
            <>
              {problem.message} <Link to={signInLink}>Sign in instead</Link>
            </>
          )
        }
      />
      <TextField
        label="Password"
        type="password"
        name="password"
        autoComplete="new-password"
        required
        minLength={PASSWORD_MIN_LENGTH}
        maxLength={128}
        hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
        value={password}
        onChange={(event) => {
          setPassword(event.target.value);
        }}
      />
      <Button type="submit" variant="primary" disabled={signUp.isPending}>
        {signUp.isPending ? "Creating your account…" : "Create account"}
      </Button>
      <p className={styles.footer}>
        Already have an account? <Link to={signInLink}>Sign in</Link>
      </p>
    </form>
  );
}
