export type Theme = "light" | "dark";

const STORAGE_KEY = "joblens_theme";

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// The user's explicit choice from the toggle, if they've ever used it. null
// means no override exists yet -- the theme should follow the OS/browser
// preference, not default to a fixed value.
export function getExplicitTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "dark" || stored === "light" ? stored : null;
}

// The theme actually in effect right now: the explicit override if one
// exists, otherwise whatever the OS/browser currently prefers.
export function getEffectiveTheme(): Theme {
  return getExplicitTheme() ?? (systemPrefersDark() ? "dark" : "light");
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

// Sets an explicit override (what the toggle calls) -- from this point on,
// the site no longer follows OS changes for this browser until the
// override is cleared.
export function setExplicitTheme(theme: Theme): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, theme);
  applyTheme(theme);
}

// Inlined verbatim as a blocking <script> in _document.tsx (must run
// before first paint, so it can't be a normal React effect -- an effect
// runs after the initial HTML is already visible, which would show a flash
// of the wrong theme). Kept here as the single source of truth for the
// logic; _document.tsx's copy must match this exactly if it's ever changed.
// Mirrors getEffectiveTheme() above in plain JS, since that function itself
// can't run this early (React hasn't hydrated yet).
export const THEME_BOOT_SCRIPT = `
try {
  var stored = localStorage.getItem("${STORAGE_KEY}");
  var isDark = stored === "dark" || (stored !== "light" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (isDark) document.documentElement.classList.add("dark");
} catch (e) {}
`;
