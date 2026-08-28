// Shared heading treatments so semantically-equivalent content renders at a
// consistent size wherever it appears, instead of each component picking
// its own text-* size ad hoc (e.g. the same "job title" content used to
// render at three different sizes depending on which tab it showed up in).

// Marketing-style hero headline. Homepage only. Sized to match PAGE_TITLE
// exactly (same text-3xl/sm:text-4xl) per explicit request -- keeps its own
// max-w since, unlike PAGE_TITLE's usages, the hero has no surrounding
// max-w wrapper of its own in index.tsx.
export const HERO_TITLE = "max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl";

// h1 on every other top-level page (/profile, /404, /terms, /privacy, and
// any future simple page).
export const PAGE_TITLE = "text-3xl font-bold tracking-tight sm:text-4xl";

// h2: job titles on primary browsing surfaces (search results, Favorites,
// Recently Viewed -- anywhere JobCard renders directly), and section
// headings within a page (e.g. legal-document sections).
export const SECTION_TITLE = "text-xl font-semibold";

// h2: job titles inside denser profile list rows (Applications, Notes,
// Hidden) that show one job per compact row alongside status/notes UI.
export const COMPACT_TITLE = "text-lg font-semibold";
