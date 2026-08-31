interface LogoProps {
  className?: string;
  showTagline?: boolean;
}

export function Logo({ className = "", showTagline = false }: LogoProps) {
  return (
    <span className={`inline-flex flex-col ${className}`}>
      <span className="inline-flex items-baseline font-bold tracking-tight text-ink-primary">
        <span>J</span>
        <MagnifyingGlassO />
        <span>bLens</span>
      </span>

      {showTagline && (
        <span className="text-[0.65rem] font-medium uppercase tracking-[0.2em] text-ink-muted">
          Job Market Transparency
        </span>
      )}
    </span>
  );
}

function MagnifyingGlassO() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="mx-[0.03em] inline-block h-[0.62em] w-[0.62em] -translate-y-[0.06em] align-baseline text-accent"
    >
      <circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" strokeWidth="2.8" />
      <line
        x1="15.4"
        y1="15.4"
        x2="21.5"
        y2="21.5"
        stroke="currentColor"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
