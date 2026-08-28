/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    // lib/typography.ts exports shared class-name strings (HERO_TITLE,
    // PAGE_TITLE, etc.) referenced dynamically via className={CONST} --
    // Tailwind only sees literal class text in scanned files, so without
    // this glob it silently generates no CSS for anything defined only
    // here, no matter what the constant is set to.
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
