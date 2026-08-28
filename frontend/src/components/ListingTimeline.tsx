import { buildTimeline } from "@/lib/jobFormatting";
import type { JobDetail } from "@/types/jobs";

function relativeDate(iso: string): string {
  const parsed = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(parsed.getTime())) return "";
  // timeZone pinned to UTC so this agrees between SSR (container, UTC) and
  // hydration (the visitor's local zone) -- see postingDateLabel in
  // jobFormatting.ts for the full explanation.
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

// Merges JobEvent + RepostEvent history (both already returned by the
// detail endpoint) into a single vertical timeline -- directly serves the
// "preserves listing history" part of the mission, previously fetched by
// the backend and silently discarded by the frontend types.
export function ListingTimeline({ job }: { job: JobDetail }) {
  const entries = buildTimeline(job);

  if (entries.length === 0) return null;

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Listing history</p>

      <ol className="mt-3 space-y-0">
        {entries.map((entry, index) => (
          <li key={entry.key} className="relative flex gap-3 pb-4 last:pb-0">
            {index < entries.length - 1 && (
              <span aria-hidden="true" className="absolute left-[5px] top-3 h-full w-px bg-slate-700" />
            )}
            <span
              aria-hidden="true"
              className="relative z-10 mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 border-cyan-300 bg-slate-900"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="text-sm font-medium text-slate-200">{entry.label}</p>
                <p className="shrink-0 text-xs text-slate-500">{relativeDate(entry.date)}</p>
              </div>
              {entry.detail && <p className="mt-0.5 text-xs leading-5 text-slate-400">{entry.detail}</p>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
