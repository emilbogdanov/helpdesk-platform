import { describe, expect, it } from "vitest";

import { formatRelative } from "@/lib/format";

const NOW = new Date("2026-10-18T14:00:00Z");

describe("formatRelative", () => {
  it.each([
    ["2026-10-18T13:59:30Z", "just now"],
    ["2026-10-18T13:55:00Z", "5 minutes ago"],
    ["2026-10-18T11:00:00Z", "3 hours ago"],
    ["2026-10-17T09:00:00Z", "yesterday"],
    ["2026-10-04T14:00:00Z", "2 weeks ago"],
    ["2026-07-18T14:00:00Z", "3 months ago"],
  ])("describes %s as %s", (iso, expected) => {
    expect(formatRelative(iso, NOW)).toBe(expected);
  });
});
