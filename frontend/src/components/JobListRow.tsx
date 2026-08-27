import { CompanyLogo } from "@/components/CompanyLogo";
import { CheckIcon, CloseIcon, IconButton, IconToggleButton, StarIcon } from "@/components/JobActionIcons";
import { confidenceLabel } from "@/lib/jobFormatting";
import { useJobActions } from "@/lib/useJobActions";
import type { JobListItem } from "@/types/jobs";

interface JobListRowProps {
  job: JobListItem;
  selected: boolean;
  onSelect: () => void;
  onDismissed?: (jobId: number) => void;
  onFavoriteChange?: (jobId: number, favorited: boolean) => void;
  onAppliedChange?: (jobId: number, applied: boolean) => void;
}

export function JobListRow({
  job,
  selected,
  onSelect,
  onDismissed,
  onFavoriteChange,
  onAppliedChange,
}: JobListRowProps) {
  const { favorited, applied, dismissed, favoritePending, appliedPending, dismissPending, toggleFavorite, toggleApplied, dismiss } =
    useJobActions(job, { onFavoriteChange, onAppliedChange, onDismissed });

  if (dismissed) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-sm text-slate-400">
        Hidden.
      </div>
    );
  }

  const confidence = job.active_hiring_confidence;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      aria-current={selected ? "true" : undefined}
      className={`flex w-full cursor-pointer items-start gap-3 rounded-xl border p-4 text-left outline-none ring-cyan-300 transition focus-visible:ring-2 ${
        selected
          ? "border-cyan-400/60 bg-cyan-950/20"
          : "border-slate-800 bg-slate-900/70 hover:border-slate-700"
      }`}
    >
      <CompanyLogo name={job.company.name} logoUrl={job.company.logo_url} size={36} />

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold text-slate-100">{job.title_raw}</p>
            <p className="truncate text-sm text-slate-300">{job.company.name}</p>
          </div>

          <span className={`confidence shrink-0 !text-base ${confidence == null ? "unknown" : confidence >= 70 ? "high" : confidence >= 45 ? "medium" : "low"}`}>
            {confidence == null ? "N/A" : Math.round(confidence)}
          </span>
        </div>

        <p className="mt-1 truncate text-xs text-slate-400">
          {job.location_raw || job.remote_type || "Location unavailable"}
          {job.job_family ? ` · ${job.job_family}` : ""}
          {job.seniority ? ` · ${job.seniority}` : ""}
        </p>

        <p className="mt-1 text-xs text-slate-500">{confidenceLabel(confidence)}</p>

        <div
          className="mt-2 flex items-center gap-1"
          onClick={(event) => event.stopPropagation()}
        >
          <IconToggleButton
            pressed={favorited}
            pending={favoritePending}
            onClick={toggleFavorite}
            labelWhenOff="Add to favorites"
            labelWhenOn="Remove from favorites"
            icon={<StarIcon filled={favorited} />}
          />
          <IconToggleButton
            pressed={applied}
            pending={appliedPending}
            onClick={toggleApplied}
            labelWhenOff="Mark as applied"
            labelWhenOn="Marked as applied. Click to undo."
            icon={<CheckIcon />}
          />
          <IconButton pending={dismissPending} onClick={dismiss} label="Hide this listing" icon={<CloseIcon />} />
        </div>
      </div>
    </div>
  );
}
