import { CARD } from "@/lib/designSystem";

export function TabLoading() {
  return (
    <div className="grid gap-4" aria-label="Loading">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className={`h-24 animate-pulse ${CARD}`} />
      ))}
    </div>
  );
}

export function TabError({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-lg border border-negative/40 bg-negative/10 p-4 text-negative">
      {message}
    </p>
  );
}

export function TabEmpty({ message }: { message: string }) {
  return (
    <div className={`${CARD} flex flex-col items-center gap-3 p-8 text-center`}>
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-9 w-9 text-ink-faint">
        <path
          d="M4 12.5V18a1 1 0 001 1h14a1 1 0 001-1v-5.5M4 12.5L6.5 5h11L20 12.5M4 12.5h5a1 1 0 011 1v.5a2 2 0 002 2h0a2 2 0 002-2v-.5a1 1 0 011-1h5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <p className="text-sm text-ink-muted">{message}</p>
    </div>
  );
}
