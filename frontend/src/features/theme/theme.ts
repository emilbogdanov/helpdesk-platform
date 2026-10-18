export const themePreferences = ["system", "light", "dark"] as const;
export type ThemePreference = (typeof themePreferences)[number];

const STORAGE_KEY = "helpdesk.theme";

export function loadThemePreference(storage: Storage | null): ThemePreference {
  try {
    const saved = storage?.getItem(STORAGE_KEY);
    return themePreferences.find((preference) => preference === saved) ?? "system";
  } catch {
    return "system";
  }
}

export function saveThemePreference(storage: Storage | null, preference: ThemePreference): void {
  try {
    storage?.setItem(STORAGE_KEY, preference);
  } catch {
    // Not remembered across visits; the choice still applies to this page.
  }
}

// "system" removes the attribute so the stylesheet follows prefers-color-scheme.
export function applyThemePreference(root: HTMLElement, preference: ThemePreference): void {
  if (preference === "system") {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = preference;
  }
}
