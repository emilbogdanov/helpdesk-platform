import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { ActivityChart } from "@/features/admin/ActivityChart";
import { useTicketStats, type TicketStats } from "@/features/admin/api";
import styles from "@/features/admin/DashboardPage.module.css";
import { formatDuration } from "@/lib/format";
import { Button } from "@/ui/Button";
import { PageState } from "@/ui/PageState";

const windows = [7, 14, 30] as const;

export function DashboardPage() {
  const [search, setSearch] = useSearchParams();
  const days = windows.find((option) => String(option) === search.get("days")) ?? 14;
  const stats = useTicketStats(days);

  return (
    <section className={styles.page} aria-labelledby="dashboard-heading">
      <div className={styles.header}>
        <h1 id="dashboard-heading" className={styles.heading}>
          Dashboard
        </h1>
        <select
          aria-label="Period"
          className={styles.period}
          value={days}
          onChange={(event) => {
            setSearch({ days: event.target.value });
          }}
        >
          {windows.map((option) => (
            <option key={option} value={option}>
              Last {option} days
            </option>
          ))}
        </select>
      </div>

      {stats.isPending ? (
        <PageState title="Loading the numbers…" busy />
      ) : stats.isError ? (
        <PageState title="Couldn't load the dashboard">
          <p>The helpdesk didn't answer. Try again in a moment.</p>
          <Button onClick={() => void stats.refetch()}>Try again</Button>
        </PageState>
      ) : (
        <Overview stats={stats.data} days={days} />
      )}
    </section>
  );
}

function Overview({ stats, days }: { stats: TicketStats; days: number }) {
  const median = stats.median_first_response_seconds;
  const opened = stats.days.reduce((sum, day) => sum + day.opened, 0);
  const resolved = stats.days.reduce((sum, day) => sum + day.resolved, 0);

  return (
    <>
      <dl className={styles.tiles}>
        <Tile label="Open" value={stats.by_status.open ?? 0} />
        <Tile label="In progress" value={stats.by_status.in_progress ?? 0} />
        <Tile label="Waiting on customer" value={stats.by_status.waiting_on_customer ?? 0} />
        <Tile label="Unassigned" value={stats.unassigned} note="open, in progress or waiting" />
        <Tile
          label="Awaiting a first reply"
          value={stats.awaiting_first_response}
          note={
            stats.first_response_overdue > 0 ? (
              <span className={styles.overdue}>{stats.first_response_overdue} past the target</span>
            ) : (
              "none past the target"
            )
          }
        />
        <Tile
          label="Median first reply"
          value={median === null ? "No replies yet" : formatDuration(median)}
          note={`tickets opened in the last ${String(days)} days`}
        />
      </dl>

      <section className={styles.panel} aria-labelledby="activity-heading">
        <div className={styles.panelHeader}>
          <h2 id="activity-heading" className={styles.panelHeading}>
            Opened and resolved per day
          </h2>
          <ul className={styles.legend} aria-label="Legend">
            <li>
              <span className={styles.swatchOpened} /> Opened <strong>{opened}</strong>
            </li>
            <li>
              <span className={styles.swatchResolved} /> Resolved <strong>{resolved}</strong>
            </li>
          </ul>
        </div>
        <ActivityChart days={stats.days} />
        <details className={styles.numbers}>
          <summary>Show the numbers</summary>
          <table>
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col">Opened</th>
                <th scope="col">Resolved</th>
              </tr>
            </thead>
            <tbody>
              {stats.days.map((day) => (
                <tr key={day.day}>
                  <th scope="row">{day.day}</th>
                  <td>{day.opened}</td>
                  <td>{day.resolved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>
    </>
  );
}

function Tile({ label, value, note }: { label: string; value: number | string; note?: ReactNode }) {
  return (
    <div className={styles.tile}>
      <dt className={styles.tileLabel}>{label}</dt>
      <dd className={styles.tileValue}>{value}</dd>
      {note && <dd className={styles.tileNote}>{note}</dd>}
    </div>
  );
}
