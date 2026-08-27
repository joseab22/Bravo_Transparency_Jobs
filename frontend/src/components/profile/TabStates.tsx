export function TabLoading() {
  return (
    <div className="grid gap-4" aria-label="Loading">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-xl border border-slate-800 bg-slate-900/70"
        />
      ))}
    </div>
  );
}

export function TabError({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-red-200">
      {message}
    </p>
  );
}

export function TabEmpty({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center text-sm text-slate-400">
      {message}
    </div>
  );
}
