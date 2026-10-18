// Merely reading window.localStorage throws when the browser blocks site data, so callers
// get null and carry on without persistence.
export function browserStorage(kind: "localStorage" | "sessionStorage"): Storage | null {
  try {
    return window[kind];
  } catch {
    return null;
  }
}
