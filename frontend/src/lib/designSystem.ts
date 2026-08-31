// Shared surface treatments so every card/panel in the app reads as one
// consistent design language instead of each component picking its own
// border color, opacity, and radius ad hoc. Concretely fixes: most cards
// used a translucent bg-surface/NN over the bg-page background with a
// border-line-subtle (one step lighter than the background), which read as
// barely-there -- the same issue fixed for the job detail panel
// specifically before this pass generalized it everywhere. Uses the
// semantic theme tokens from tailwind.config.js/globals.css, so these
// render correctly in both light and dark mode with no dark: variants needed.

// Standard bordered card/panel, in normal page flow (job cards, profile
// rows, filter panels, callouts). Solid background, visible border.
export const CARD = "rounded-xl border border-line bg-surface";

// A card that sits apart from normal flow -- sticky/floating panels,
// dropdowns -- gets a shadow on top of CARD for a sense of elevation.
export const ELEVATED_CARD = `${CARD} shadow-lg shadow-black/30`;

// Denser row variant (compact list rows, small inline cards).
export const COMPACT_CARD = "rounded-xl border border-line bg-surface";

// Inline pill/tag/badge (source links, fact chips).
export const PILL = "rounded-full border border-line px-3 py-1 text-xs font-medium";
