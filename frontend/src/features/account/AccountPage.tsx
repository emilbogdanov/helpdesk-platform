import styles from "@/features/account/AccountPage.module.css";
import { useCurrentUserProfile } from "@/features/auth/current-user";

const memberSince = new Intl.DateTimeFormat(undefined, { dateStyle: "long" });

const roleDescriptions = {
  customer: "Customer: you can open tickets and follow your own conversations.",
  agent: "Agent: you work the shared queue and can write internal notes.",
  admin: "Admin: agent access plus managing accounts and roles.",
} as const;

export function AccountPage() {
  const user = useCurrentUserProfile();

  return (
    <section className={styles.page} aria-labelledby="account-heading">
      <h1 id="account-heading" className={styles.heading}>
        Account
      </h1>
      <dl className={styles.details}>
        <dt>Name</dt>
        <dd>{user.display_name}</dd>
        <dt>Email</dt>
        <dd>{user.email}</dd>
        <dt>Access</dt>
        <dd>{roleDescriptions[user.role]}</dd>
        <dt>Member since</dt>
        <dd>
          <time dateTime={user.created_at}>{memberSince.format(new Date(user.created_at))}</time>
        </dd>
      </dl>
    </section>
  );
}
