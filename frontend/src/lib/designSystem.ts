// Shared surface treatments so every card/panel in the app reads as one
// consistent design language instead of each component picking its own
// border color, opacity, and radius ad hoc. Concretely fixes: most cards
// used a translucent bg-slate-900/NN over the bg-slate-950 page background
// with a border-slate-800 (one step lighter than the background), which
// reads as barely-there -- the same issue fixed for the job detail panel
// specifically before this pass generalized it everywhere.

// Standard bordered card/panel, in normal page flow (job cards, profile
// rows, filter panels, callouts). Solid background, visible border.
export const CARD = "rounded-xl border border-slate-700 bg-slate-900";

// A card that sits apart from normal flow -- sticky/floating panels,
// dropdowns -- gets a shadow on top of CARD for a sense of elevation.
export const ELEVATED_CARD = `${CARD} shadow-lg shadow-black/30`;

// Denser row variant (compact list rows, small inline cards).
export const COMPACT_CARD = "rounded-xl border border-slate-700 bg-slate-900";

// Inline pill/tag/badge (source links, fact chips).
export const PILL = "rounded-full border border-slate-700 px-3 py-1 text-xs font-medium";
