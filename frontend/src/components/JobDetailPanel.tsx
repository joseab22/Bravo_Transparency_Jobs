import { useEffect, useState } from "react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { CheckIcon, CloseIcon, IconButton, IconToggleButton, NoteIcon, StarIcon } from "@/components/JobActionIcons";
import { ScoreReasoningTooltip } from "@/components/ScoreReasoningTooltip";
import { jobsApi, meApi } from "@/lib/api";
import { ageSummary, formatSalary, postingDateLabel, safeExternalUrl, sourceLinks } from "@/lib/jobFormatting";
import { useJobActions } from "@/lib/useJobActions";
import { SECTION_TITLE } from "@/lib/typography";
import type { JobDetail, JobListItem } from "@/types/jobs";

interface JobDetailPanelProps {
  jobId: number | null;
  fallback: JobListItem | null;
  // Passed through to the detail fetch so "Found on" excludes source URLs
  // older than the active age filter, matching the list view instead of
  // silently ignoring it (the list and detail requests must agree, or a
  // listing appears to have different evidence depending on which view you
  // opened it from).
  maxAgeDays?: number;
  onFavoriteChange?: (jobId: number, favorited: boolean) => void;
  onAppliedChange?: (jobId: number, applied: boolean) => void;
  onDismissed?: (jobId: number) => void;
}

export function JobDetailPanel({ jobId, fallback, maxAgeDays, onFavoriteChange, onAppliedChange, onDismissed }: JobDetailPanelProps) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetail(null);
    setError(null);

    if (jobId == null) return;

    let cancelled = false;
    setLoading(true);

    void meApi.recordView(jobId).catch(() => {
      // Recording a view is a soft signal; a failure here shouldn't block the detail view.
    });

    jobsApi
      .get(jobId, maxAgeDays)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load this job.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [jobId, maxAgeDays]);

  if (jobId == null) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-900 p-8 text-center text-sm text-slate-400 shadow-lg shadow-black/30">
        Select a listing to see its full details here.
      </div>
    );
  }

  const job = detail ?? fallback;

  if (!job && loading) {
    return (
      <div className="animate-pulse rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/30">
        <div className="h-6 w-2/3 rounded bg-slate-800" />
        <div className="mt-3 h-4 w-1/2 rounded bg-slate-800" />
        <div className="mt-6 h-24 rounded bg-slate-800" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-200">
        {error ?? "Unable to load this job."}
      </div>
    );
  }

  return <JobDetailContent job={job} loadingMore={loading && !detail} error={error} onFavoriteChange={onFavoriteChange} onAppliedChange={onAppliedChange} onDismissed={onDismissed} />;
}

interface JobDetailContentProps {
  job: JobListItem | JobDetail;
  loadingMore: boolean;
  error: string | null;
  onFavoriteChange?: (jobId: number, favorited: boolean) => void;
  onAppliedChange?: (jobId: number, applied: boolean) => void;
  onDismissed?: (jobId: number) => void;
}

function JobDetailContent({ job, loadingMore, error, onFavoriteChange, onAppliedChange, onDismissed }: JobDetailContentProps) {
  const {
    favorited,
    applied,
    dismissed,
    favoritePending,
    appliedPending,
    dismissPending,
    actionError,
    actionFeedback,
    toggleFavorite,
    toggleApplied,
    dismiss,
  } = useJobActions(job, { onFavoriteChange, onAppliedChange, onDismissed });

  const [savedNote, setSavedNote] = useState(job.note ?? "");
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState(job.note ?? "");
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [noteFeedback, setNoteFeedback] = useState<string | null>(null);

  useEffect(() => {
    setSavedNote(job.note ?? "");
    setNoteText(job.note ?? "");
    setNoteOpen(false);
    setNoteError(null);
    setNoteFeedback(null);
  }, [job.id, job.note]);

  const noteDirty = noteText !== savedNote;

  async function saveNote() {
    setNoteSaving(true);
    setNoteError(null);
    setNoteFeedback(null);
    try {
      const trimmed = noteText.trim();
      if (trimmed) {
        await meApi.upsertNote(job.id, trimmed);
      } else {
        await meApi.removeNote(job.id);
      }
      setSavedNote(trimmed);
      setNoteText(trimmed);
      setNoteFeedback(trimmed ? "Saved." : "Note removed.");
    } catch {
      setNoteError("Could not save this note. Try again.");
    } finally {
      setNoteSaving(false);
    }
  }

  if (dismissed) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-900 p-4 text-sm text-slate-400 shadow-lg shadow-black/30">
        Hidden. It will not appear in search results again.
      </div>
    );
  }

  const detail = "description_raw" in job ? (job as JobDetail) : null;
  const salary = formatSalary(job);
  const postedOn = postingDateLabel(job);

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/30">
      <div className="flex items-start gap-3">
        <CompanyLogo name={job.company.name} logoUrl={job.company.logo_url} size={48} />

        <div className="min-w-0 flex-1">
          <h2 className={SECTION_TITLE}>{job.title_raw}</h2>
          <p className="mt-1 text-slate-300">
            {job.company.name} · {job.location_raw || job.remote_type || "Location unavailable"}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1">
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
          <IconToggleButton
            pressed={savedNote.length > 0}
            pending={noteSaving}
            onClick={() => setNoteOpen((open) => !open)}
            labelWhenOff="Add a note"
            labelWhenOn="Edit note"
            icon={<NoteIcon />}
          />
          <IconButton pending={dismissPending} onClick={dismiss} label="Hide this listing" icon={<CloseIcon />} />
        </div>
      </div>

      {noteOpen && (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <label className="block text-sm text-slate-300">
            Note
            <textarea
              value={noteText}
              onChange={(event) => setNoteText(event.target.value)}
              rows={3}
              placeholder="Add a personal note about this listing..."
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
            />
          </label>
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={saveNote}
              disabled={!noteDirty || noteSaving}
              className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {noteSaving ? "Saving…" : "Save note"}
            </button>
            {noteFeedback && <span className="text-sm text-emerald-300">{noteFeedback}</span>}
            {noteError && (
              <span role="alert" className="text-sm text-rose-300">
                {noteError}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          {[job.job_family || "Unknown role type", job.seniority, job.employment_type, job.remote_type, salary]
            .filter((fact): fact is string => Boolean(fact))
            .map((fact) => (
              <span
                key={fact}
                className="rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs font-medium text-slate-300"
              >
                {fact}
              </span>
            ))}
        </div>

        <ScoreReasoningTooltip job={job} />
      </div>

      {(actionFeedback || actionError) && (
        <p role={actionError ? "alert" : "status"} className={`mt-2 text-xs ${actionError ? "text-rose-300" : "text-emerald-300"}`}>
          {actionError || actionFeedback}
        </p>
      )}

      <p className="mt-4 text-xs text-slate-500">
        {job.listing_classification}
        {job.repost_count > 0 ? ` · repost #${job.repost_count}` : ""}
        {` · ${ageSummary(job)}`}
        {postedOn ? ` · posted ${postedOn}` : ""}
        {job.applicant_count != null ? ` · ${job.applicant_count} reported applicants` : ""}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-400">Found on</span>

        {sourceLinks(job).map(({ source, label }) => {
          const safeUrl = safeExternalUrl(source.source_url);

          return safeUrl ? (
            <a
              key={source.sighting_key}
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              title={`Open this listing on ${source.publisher_name}`}
              className="rounded-full border border-cyan-500/40 bg-cyan-950/30 px-3 py-1 text-cyan-200 hover:border-cyan-300"
            >
              {label}
              {source.is_direct ? " · Direct" : ""}
            </a>
          ) : (
            <span
              key={source.sighting_key}
              title="The source URL was unavailable or invalid"
              className="rounded-full border border-slate-700 px-3 py-1 text-slate-300"
            >
              {label}
              {source.is_direct ? " · Direct" : ""}
            </span>
          );
        })}
      </div>

      <div className="mt-6 border-t border-slate-800 pt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</p>

        {loadingMore && !detail && (
          <div className="mt-2 animate-pulse space-y-2">
            <div className="h-3 w-full rounded bg-slate-800" />
            <div className="h-3 w-5/6 rounded bg-slate-800" />
            <div className="h-3 w-2/3 rounded bg-slate-800" />
          </div>
        )}

        {!loadingMore && detail?.description_raw && (
          <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-300">
            {detail.description_raw}
          </p>
        )}

        {!loadingMore && detail && !detail.description_raw && (
          <p className="mt-2 text-sm text-slate-500">
            No description was available from the source listing.
          </p>
        )}

        {error && (
          <p role="alert" className="mt-2 text-sm text-rose-300">
            {error}
          </p>
        )}

        {detail && (detail.department || detail.education_required || detail.experience_years_min != null) && (
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            {detail.department && (
              <div>
                <dt className="text-slate-500">Department</dt>
                <dd className="text-slate-300">{detail.department}</dd>
              </div>
            )}
            {detail.education_required && (
              <div>
                <dt className="text-slate-500">Education</dt>
                <dd className="text-slate-300">{detail.education_required}</dd>
              </div>
            )}
            {(detail.experience_years_min != null || detail.experience_years_max != null) && (
              <div>
                <dt className="text-slate-500">Experience</dt>
                <dd className="text-slate-300">
                  {detail.experience_years_min ?? 0}
                  {detail.experience_years_max != null ? `-${detail.experience_years_max}` : "+"} years
                </dd>
              </div>
            )}
          </dl>
        )}
      </div>
    </div>
  );
}
