// Magnitude comparison, low->high: one sequential hue, thin bars, direct
// labels (count) so the value never depends on reading bar length alone.
// Plain HTML/CSS bars rather than an SVG/canvas chart -- appropriate for a
// short, static ranked list (dataviz method: "sequential is the safe
// default... stays legible and consistent").
export function BarList({ items, maxItems = 10 }: { items: { label: string; count: number }[]; maxItems?: number }) {
  const rows = items.slice(0, maxItems);
  const max = Math.max(...rows.map((row) => row.count), 1);

  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No data available yet.</p>;
  }

  return (
    <ul className="space-y-2.5">
      {rows.map((row) => (
        <li key={row.label} className="flex items-center gap-3 text-sm">
          <span className="w-36 shrink-0 truncate text-slate-300" title={row.label}>
            {row.label}
          </span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
            <span
              className="block h-full rounded-full bg-cyan-400"
              style={{ width: `${Math.max((row.count / max) * 100, 4)}%` }}
            />
          </span>
          <span className="w-12 shrink-0 text-right font-medium text-slate-200">{row.count.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}
