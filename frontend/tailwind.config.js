/** @type {import('tailwindcss').Config} */
module.exports = {
  // Class-based, not media-query-based: the app defaults to light mode
  // regardless of OS preference, with an explicit toggle persisted by the
  // user (see lib/theme.ts) -- `media` would make dark mode follow the OS
  // setting instead of the toggle.
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    // lib/typography.ts and lib/designSystem.ts export shared class-name
    // strings referenced dynamically via className={CONST} -- Tailwind
    // only sees literal class text in scanned files, so without this glob
    // it silently generates no CSS for anything defined only here, no
    // matter what the constant is set to.
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ghost: {
          low: "#3B6D11",
          med: "#854F0B",
          high: "#A32D2D",
        },
        // Semantic, theme-aware tokens. Each resolves through a CSS custom
        // property (see globals.css :root vs .dark) so the same class name
        // -- e.g. bg-surface -- renders the light or dark value depending
        // on the .dark class on <html>, without any dark: prefix needed at
        // the call site. The space-separated triplet + <alpha-value> lets
        // Tailwind's opacity modifiers (bg-accent/10, border-negative/40)
        // work the same way they would on a built-in color.
        page: "rgb(var(--page) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-2": "rgb(var(--surface-2) / <alpha-value>)",
        inset: "rgb(var(--inset) / <alpha-value>)",
        line: {
          DEFAULT: "rgb(var(--line) / <alpha-value>)",
          subtle: "rgb(var(--line-subtle) / <alpha-value>)",
          strong: "rgb(var(--line-strong) / <alpha-value>)",
        },
        ink: {
          primary: "rgb(var(--ink-primary) / <alpha-value>)",
          secondary: "rgb(var(--ink-secondary) / <alpha-value>)",
          muted: "rgb(var(--ink-muted) / <alpha-value>)",
          faint: "rgb(var(--ink-faint) / <alpha-value>)",
          onaccent: "rgb(var(--ink-onaccent) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          solid: "rgb(var(--accent-solid) / <alpha-value>)",
          "solid-hover": "rgb(var(--accent-solid-hover) / <alpha-value>)",
        },
        positive: "rgb(var(--positive) / <alpha-value>)",
        negative: "rgb(var(--negative) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
      },
      fontFamily: {
        // No sans override: Tailwind's own default sans-serif stack (which
        // leads with system-ui) is the deliberately chosen font here, not a
        // fallback -- see globals.css.
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
