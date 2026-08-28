import { useState, type ReactNode } from "react";

interface TooltipProps {
  label: string;
  children: ReactNode;
}

// Wraps a single focusable child (a button, typically) with a visible label
// tooltip. Works on hover, keyboard focus, and tap/click -- native `title`
// attributes only reliably cover hover, so icon-only controls (favorite,
// note, dismiss, etc.) need this instead of `title` to stay accessible on
// touch devices and for keyboard users.
export function Tooltip({ label, children }: TooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <span
      className="group relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
      onClick={() => setOpen(true)}
    >
      {children}
      <span
        role="tooltip"
        // Icon buttons using this sit at the top of their card, so opening
        // upward (like a typical tooltip) clips against the card's own top
        // edge or the card above it in the list. Opens downward instead,
        // matching ScoreReasoningTooltip in the same position.
        className={`pointer-events-none absolute left-1/2 top-full z-50 mt-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-100 shadow-xl transition ${
          open ? "opacity-100" : "invisible opacity-0"
        }`}
      >
        {label}
      </span>
    </span>
  );
}
