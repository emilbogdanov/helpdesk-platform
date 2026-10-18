import { useState } from "react";

import {
  applyThemePreference,
  loadThemePreference,
  saveThemePreference,
  themePreferences,
  type ThemePreference,
} from "@/features/theme/theme";
import styles from "@/features/theme/ThemeSelect.module.css";
import { browserStorage } from "@/lib/storage";

const labels: Record<ThemePreference, string> = {
  system: "System theme",
  light: "Light",
  dark: "Dark",
};

export function ThemeSelect() {
  const [preference, setPreference] = useState(() =>
    loadThemePreference(browserStorage("localStorage")),
  );

  function choose(next: ThemePreference) {
    setPreference(next);
    saveThemePreference(browserStorage("localStorage"), next);
    applyThemePreference(document.documentElement, next);
  }

  return (
    <select
      aria-label="Theme"
      className={styles.select}
      value={preference}
      onChange={(event) => {
        const next = themePreferences.find((option) => option === event.target.value);
        if (next) {
          choose(next);
        }
      }}
    >
      {themePreferences.map((option) => (
        <option key={option} value={option}>
          {labels[option]}
        </option>
      ))}
    </select>
  );
}
