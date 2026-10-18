const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
// English like the rest of the interface, so "3 hours ago" never sits in a sentence of another language.
const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const MINUTES_IN: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60],
  ["month", 30 * 24 * 60],
  ["week", 7 * 24 * 60],
  ["day", 24 * 60],
  ["hour", 60],
  ["minute", 1],
];

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

// "3 hours ago", "in 1 hour", "yesterday"; anything under a minute is "just now". Rounded
// to whole minutes first, so 59 minutes 58 seconds reads as "in 1 hour".
export function formatRelative(iso: string, now: Date = new Date()): string {
  const minutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000);
  for (const [unit, size] of MINUTES_IN) {
    if (Math.abs(minutes) >= size) {
      return relative.format(Math.round(minutes / size), unit);
    }
  }
  return "just now";
}
