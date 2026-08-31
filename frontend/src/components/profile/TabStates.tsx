export function TabLoading() {
  return (
    <div className="grid gap-4" aria-label="Loading">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-xl border border-line-subtle bg-surface"
        />
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
    <div className="rounded-xl border border-line-subtle bg-surface p-8 text-center text-sm text-ink-muted">
      {message}
    </div>
  );
}
