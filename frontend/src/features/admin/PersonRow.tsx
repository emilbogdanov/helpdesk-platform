import { useState } from "react";

import type { User } from "@/api/types";
import { useChangeRole, useSetActive } from "@/features/admin/api";
import { accountErrorMessage } from "@/features/admin/errors";
import styles from "@/features/admin/PeoplePage.module.css";
import { roleNames, roles } from "@/features/admin/roles";
import { formatDate } from "@/lib/format";
import { Button } from "@/ui/Button";
import { classNames } from "@/ui/class-names";

export function PersonRow({ person, isViewer }: { person: User; isViewer: boolean }) {
  const changeRole = useChangeRole();
  const setActive = useSetActive();
  const [confirming, setConfirming] = useState(false);
  const busy = changeRole.isPending || setActive.isPending;
  const error = changeRole.error ?? setActive.error;

  return (
    <tr className={person.is_active ? undefined : styles.inactive}>
      <th scope="row" className={styles.name}>
        {person.display_name}
        {isViewer && <span className={styles.you}>You</span>}
        {error && (
          <span role="alert" className={styles.rowError}>
            {accountErrorMessage(error)}
          </span>
        )}
      </th>
      <td>{person.email}</td>
      <td>
        <select
          aria-label={`Role for ${person.display_name}`}
          className={styles.inlineSelect}
          value={person.role}
          disabled={isViewer || busy}
          onChange={(event) => {
            const role = roles.find((option) => option === event.target.value);
            if (role) {
              changeRole.mutate({ userId: person.id, role });
            }
          }}
        >
          {roles.map((role) => (
            <option key={role} value={role}>
              {roleNames[role]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <span className={classNames(styles.state, !person.is_active && styles.off)}>
          {person.is_active ? "Active" : "Deactivated"}
        </span>
      </td>
      <td className={styles.joined}>
        <time dateTime={person.created_at}>{formatDate(person.created_at)}</time>
      </td>
      <td className={styles.actions}>
        {isViewer ? null : !person.is_active ? (
          <Button
            size="sm"
            disabled={busy}
            onClick={() => {
              setActive.mutate({ userId: person.id, active: true });
            }}
          >
            Reactivate
          </Button>
        ) : confirming ? (
          <span className={styles.confirm}>
            <Button
              size="sm"
              variant="danger"
              disabled={busy}
              onClick={() => {
                setActive.mutate(
                  { userId: person.id, active: false },
                  {
                    onSettled: () => {
                      setConfirming(false);
                    },
                  },
                );
              }}
            >
              Sign {person.display_name.split(" ")[0]} out and deactivate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep
            </Button>
          </span>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Deactivate
          </Button>
        )}
      </td>
    </tr>
  );
}
