import "@fontsource-variable/inter";
import "@/styles/tokens.css";
import "@/styles/base.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";
import { applyThemePreference, loadThemePreference } from "@/features/theme/theme";
import { browserStorage } from "@/lib/storage";

// Before the first render, so a dark-theme user never sees a light flash.
applyThemePreference(document.documentElement, loadThemePreference(browserStorage("localStorage")));

const root = document.getElementById("root");
if (!root) {
  throw new Error("index.html is missing the #root element");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
