export type Theme = "light" | "dark";

const STORAGE_KEY = "joblens_theme";

// Light is the default whenever nothing is stored yet -- this deliberately
// does NOT consult prefers-color-scheme. The app's dark mode is an opt-in
// toggle, not an OS-following default; matching the boot script in
// _document.tsx, which applies this same rule before first paint.
export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "dark" ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function setStoredTheme(theme: Theme): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

// Inlined verbatim as a blocking <script> in _document.tsx (must run
// before first paint, so it can't be a normal React effect -- an effect
// runs after the initial HTML is already visible, which would show a flash
// of the wrong theme). Kept here as the single source of truth for the
// logic; _document.tsx's copy must match this exactly if it's ever changed.
export const THEME_BOOT_SCRIPT = `
try {
  var t = localStorage.getItem("${STORAGE_KEY}");
  if (t === "dark") document.documentElement.classList.add("dark");
} catch (e) {}
`;
