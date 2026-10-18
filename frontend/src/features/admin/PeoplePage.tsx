import { useState } from "react";
import { useSearchParams } from "react-router";

import { AddPersonForm } from "@/features/admin/AddPersonForm";
import { usePeople, type PeopleFilters } from "@/features/admin/api";
import styles from "@/features/admin/PeoplePage.module.css";
import { PersonRow } from "@/features/admin/PersonRow";
import { roleNames, roles } from "@/features/admin/roles";
import { useCurrentUserProfile } from "@/features/auth/current-user";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { Button } from "@/ui/Button";
import { Notice } from "@/ui/Notice";
import { PageState } from "@/ui/PageState";

const statuses = ["active", "deactivated"] as const;

export function PeoplePage() {
  const viewer = useCurrentUserProfile();
  const [search, setSearch] = useSearchParams();
  const [typed, setTyped] = useState(search.get("q") ?? "");
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState<string | null>(null);
  const settledSearch = useDebouncedValue(typed.trim(), 250);

  const filters: PeopleFilters = {
    search: settledSearch,
    role: roles.find((role) => role === search.get("role")) ?? null,
    status: statuses.find((status) => status === search.get("status")) ?? null,
  };
  const people = usePeople(filters);

  function setFilter(key: string, value: string) {
    setSearch((current) => {
      const next = new URLSearchParams(current);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      return next;
    });
  }

  const rows = people.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = filters.search !== "" || filters.role !== null || filters.status !== null;

  return (
    <section className={styles.page} aria-labelledby="people-heading">
      <div className={styles.header}>
        <h1 id="people-heading" className={styles.heading}>
          People
        </h1>
        {!adding && (
          <Button
            variant="primary"
            onClick={() => {
              setAdding(true);
              setAdded(null);
            }}
          >
            Add person
          </Button>
        )}
      </div>

      {added && <Notice tone="info">{added} can sign in now.</Notice>}
      {adding && (
        <AddPersonForm
          onAdded={(name) => {
            setAdding(false);
            setAdded(name);
          }}
          onCancel={() => {
            setAdding(false);
          }}
        />
      )}

      <div className={styles.toolbar}>
        <input
          type="search"
          aria-label="Search by name or email"
          placeholder="Search by name or email"
          className={styles.search}
          value={typed}
          onChange={(event) => {
            setTyped(event.target.value);
            setFilter("q", event.target.value.trim());
          }}
        />
        <select
          aria-label="Role"
          className={styles.filter}
          value={filters.role ?? ""}
          onChange={(event) => {
            setFilter("role", event.target.value);
          }}
        >
          <option value="">Any role</option>
          {roles.map((role) => (
            <option key={role} value={role}>
              {roleNames[role]}s
            </option>
          ))}
        </select>
        <select
          aria-label="Status"
          className={styles.filter}
          value={filters.status ?? ""}
          onChange={(event) => {
            setFilter("status", event.target.value);
          }}
        >
          <option value="">Active and deactivated</option>
          <option value="active">Active</option>
          <option value="deactivated">Deactivated</option>
        </select>
      </div>

      {people.isPending ? (
        <PageState title="Loading people…" busy />
      ) : people.isError ? (
        <PageState title="Couldn't load people">
          <p>The helpdesk didn't answer. Try again in a moment.</p>
          <Button onClick={() => void people.refetch()}>Try again</Button>
        </PageState>
      ) : rows.length === 0 ? (
        <PageState title={filtered ? "Nobody matches" : "No accounts yet"}>
          {filtered && <p>Try a shorter search or another role.</p>}
        </PageState>
      ) : (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Role</th>
                <th scope="col">Status</th>
                <th scope="col">Joined</th>
                <th scope="col">
                  <span className={styles.visuallyHidden}>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((person) => (
                <PersonRow key={person.id} person={person} isViewer={person.id === viewer.id} />
              ))}
            </tbody>
          </table>
          {people.hasNextPage && (
            <div className={styles.more}>
              <Button
                onClick={() => void people.fetchNextPage()}
                disabled={people.isFetchingNextPage}
              >
                {people.isFetchingNextPage ? "Loading…" : "Show more"}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
