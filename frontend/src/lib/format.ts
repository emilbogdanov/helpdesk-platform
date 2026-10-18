const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
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

export function formatDate(iso: string): string {
  return dateOnly.format(new Date(iso));
}

// A span of time the way people say it: "45 min", "1 h 20 min", "2 d 3 h".
export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${String(Math.max(minutes, 1))} min`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const rest = minutes % 60;
    return rest ? `${String(hours)} h ${String(rest)} min` : `${String(hours)} h`;
  }
  const days = Math.floor(hours / 24);
  const rest = hours % 24;
  return rest ? `${String(days)} d ${String(rest)} h` : `${String(days)} d`;
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
