// Only same-site paths: "//evil.example" or "https://..." in ?next= would turn the sign-in
// page into an open redirect.
export function safeNextPath(next: string | null): string {
  if (next?.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")) {
    return next;
  }
  return "/";
}

export function signInPathFor(location: { pathname: string; search: string }): string {
  const next = `${location.pathname}${location.search}`;
  return next === "/" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(next)}`;
}
