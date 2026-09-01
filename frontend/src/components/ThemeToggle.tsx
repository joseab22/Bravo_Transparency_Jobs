import { useEffect, useState } from "react";

import { applyTheme, getEffectiveTheme, getExplicitTheme, setExplicitTheme, type Theme } from "@/lib/theme";

// Reads the real effective theme after mount (the boot script in
// _document.tsx has already applied the class by then) rather than
// assuming "light" -- SSR has no access to localStorage or matchMedia, so
// this can't be known during the server render, only client-side after
// hydration.
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(getEffectiveTheme());
    setMounted(true);

    // Follow the OS/browser preference live -- but only while the user
    // hasn't made an explicit choice via this toggle. Once they have,
    // getExplicitTheme() is non-null and this listener intentionally does
    // nothing, since the override should stick regardless of what the OS
    // does afterward.
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    function handleSystemChange(event: MediaQueryListEvent) {
      if (getExplicitTheme() != null) return;
      const next: Theme = event.matches ? "dark" : "light";
      setTheme(next);
      applyTheme(next);
    }
    media.addEventListener("change", handleSystemChange);
    return () => media.removeEventListener("change", handleSystemChange);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setExplicitTheme(next);
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={isDark}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      // Suppressed during the one frame before mount, when this button's
      // own rendered icon can't yet reflect the real (localStorage/OS
      // -backed) theme -- avoids a one-frame icon flash/mismatch, distinct
      // from the page-wide dark-class flash the boot script already prevents.
      className={`rounded-lg p-2 text-ink-muted outline-none ring-accent transition hover:bg-surface-2 hover:text-ink-primary focus-visible:ring-2 ${
        mounted ? "" : "invisible"
      }`}
    >
      {isDark ? (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
          <path
            d="M20 14.5A8.5 8.5 0 1110.5 4a6.5 6.5 0 009.5 10.5z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
          <circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M12 2.5v2.5M12 19v2.5M4.5 12H2M22 12h-2.5M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      )}
    </button>
  );
}
