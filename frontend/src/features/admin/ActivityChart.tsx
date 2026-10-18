import { useRef, useState } from "react";

import styles from "@/features/admin/ActivityChart.module.css";
import { useElementWidth } from "@/lib/use-element-width";

export interface DayActivity {
  day: string;
  opened: number;
  resolved: number;
}

const HEIGHT = 200;
const MARGIN = { top: 8, right: 8, bottom: 24, left: 32 };
const MAX_BAR = 24;
const PAIR_GAP = 2;
const RADIUS = 4;

const dayLabel = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});
const weekdayLabel = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

// Opened and resolved side by side for each day. One axis, counts only; the numbers are
// also in the table below it and in each day's tooltip.
export function ActivityChart({ days }: { days: DayActivity[] }) {
  const container = useRef<HTMLDivElement>(null);
  const width = useElementWidth(container, 720);
  const [active, setActive] = useState<number | null>(null);

  const plotWidth = Math.max(width - MARGIN.left - MARGIN.right, 0);
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const ticks = yTicks(Math.max(...days.map((day) => Math.max(day.opened, day.resolved)), 0));
  const top = ticks[ticks.length - 1] ?? 1;
  const band = days.length ? plotWidth / days.length : 0;
  const bar = Math.max(Math.min(MAX_BAR, (band * 0.7 - PAIR_GAP) / 2), 2);
  const labelEvery = band < 40 ? 2 : 1;
  const y = (value: number) => MARGIN.top + plotHeight - (value / top) * plotHeight;
  const focused = active === null ? null : days[active];

  return (
    <div ref={container} className={styles.chart}>
      <svg
        width={width}
        height={HEIGHT}
        role="group"
        aria-label="Tickets opened and resolved per day"
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={MARGIN.left}
              x2={MARGIN.left + plotWidth}
              y1={y(tick)}
              y2={y(tick)}
              className={styles.grid}
            />
            <text
              x={MARGIN.left - 8}
              y={y(tick)}
              className={styles.axisLabel}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {tick}
            </text>
          </g>
        ))}
        {days.map((day, index) => {
          const left = MARGIN.left + index * band;
          const centre = left + band / 2;
          const date = new Date(`${day.day}T00:00:00Z`);
          return (
            <g key={day.day}>
              {active === index && (
                <rect
                  x={left}
                  y={MARGIN.top}
                  width={band}
                  height={plotHeight}
                  className={styles.highlight}
                />
              )}
              <path
                d={column(centre - PAIR_GAP / 2 - bar, bar, y(day.opened), y(0))}
                className={styles.opened}
              />
              <path
                d={column(centre + PAIR_GAP / 2, bar, y(day.resolved), y(0))}
                className={styles.resolved}
              />
              {/* Counted back from today, so the latest day always has its date. */}
              {(days.length - 1 - index) % labelEvery === 0 && (
                <text x={centre} y={HEIGHT - 6} className={styles.axisLabel} textAnchor="middle">
                  {dayLabel.format(date)}
                </text>
              )}
              {/* The whole day is the hit target, not just the painted bars. */}
              <rect
                x={left}
                y={MARGIN.top}
                width={band}
                height={plotHeight}
                className={styles.hit}
                tabIndex={0}
                role="img"
                aria-label={`${weekdayLabel.format(date)}: ${String(day.opened)} opened, ${String(day.resolved)} resolved`}
                onPointerEnter={() => {
                  setActive(index);
                }}
                onPointerLeave={() => {
                  setActive(null);
                }}
                onFocus={() => {
                  setActive(index);
                }}
                onBlur={() => {
                  setActive(null);
                }}
              />
            </g>
          );
        })}
        <line
          x1={MARGIN.left}
          x2={MARGIN.left + plotWidth}
          y1={y(0)}
          y2={y(0)}
          className={styles.baseline}
        />
      </svg>
      {focused && active !== null && (
        <div
          className={styles.tooltip}
          // Beside the hovered day, flipping to its left in the right half so it stays inside.
          style={
            (active + 0.5) * band > plotWidth / 2
              ? { right: width - (MARGIN.left + active * band) + 8, top: MARGIN.top }
              : { left: MARGIN.left + (active + 1) * band + 8, top: MARGIN.top }
          }
          aria-hidden="true"
        >
          <p className={styles.tooltipDay}>
            {weekdayLabel.format(new Date(`${focused.day}T00:00:00Z`))}
          </p>
          <p>
            <span className={styles.keyOpened} />
            <strong>{focused.opened}</strong> opened
          </p>
          <p>
            <span className={styles.keyResolved} />
            <strong>{focused.resolved}</strong> resolved
          </p>
        </div>
      )}
    </div>
  );
}

// A column with a rounded top and a square foot on the baseline.
function column(x: number, width: number, top: number, baseline: number): string {
  const height = baseline - top;
  if (height <= 0) {
    return "";
  }
  const r = Math.min(RADIUS, height, width / 2);
  return [
    `M${String(x)},${String(baseline)}`,
    `V${String(top + r)}`,
    `Q${String(x)},${String(top)} ${String(x + r)},${String(top)}`,
    `H${String(x + width - r)}`,
    `Q${String(x + width)},${String(top)} ${String(x + width)},${String(top + r)}`,
    `V${String(baseline)}`,
    "Z",
  ].join(" ");
}

// Whole-number ticks on a 1-2-5 step, at least four of them so a quiet fortnight still
// reads as low rather than filling the chart.
export function yTicks(max: number): number[] {
  const target = Math.max(max, 4);
  const step =
    [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000].find((size) => target / size <= 5) ??
    Math.ceil(target / 5);
  const top = Math.ceil(target / step) * step;
  return Array.from({ length: top / step + 1 }, (_, index) => index * step);
}
