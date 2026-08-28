import { useEffect, useState } from "react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { CheckIcon, CloseIcon, IconButton, IconToggleButton, NoteIcon, StarIcon } from "@/components/JobActionIcons";
import { ScoreReasoningTooltip } from "@/components/ScoreReasoningTooltip";
import { meApi } from "@/lib/api";
import {
  ageSummary,
  distinctBoardCount,
  formatSalary,
  postingDateLabel,
  safeExternalUrl,
  sourceLinks,
} from "@/lib/jobFormatting";
import { useJobActions } from "@/lib/useJobActions";
import { SECTION_TITLE } from "@/lib/typography";
import type { JobListItem } from "@/types/jobs";

interface JobCardProps {
  job: JobListItem;
  onDismissed?: (jobId: number) => void;
  onFavoriteChange?: (jobId: number, favorited: boolean) => void;
  onAppliedChange?: (jobId: number, applied: boolean) => void;
}

export function JobCard({ job, onDismissed, onFavoriteChange, onAppliedChange }: JobCardProps) {
  const [expanded, setExpanded] = useState(false);
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

  const salary = formatSalary(job);
  const boardCount = distinctBoardCount(job);
  const postedOn = postingDateLabel(job);

  if (dismissed) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
        Hidden. It will not appear in search results again.
      </div>
    );
  }

  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <CompanyLogo name={job.company.name} logoUrl={job.company.logo_url} />

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className={SECTION_TITLE}>{job.title_raw}</h2>
                <p className="mt-1 text-slate-300">
                  {job.company.name} ·{" "}
                  {job.location_raw || job.remote_type || "Location unavailable"}
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
                <IconButton
                  pending={dismissPending}
                  onClick={dismiss}
                  label="Hide this listing"
                  icon={<CloseIcon />}
                />
              </div>
            </div>

            {noteOpen && (
              <div className="mt-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
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

            <p className="mt-2 text-sm text-slate-400">
              {job.job_family || "Unknown role type"}
              {job.seniority ? ` · ${job.seniority}` : ""}
              {job.employment_type ? ` · ${job.employment_type}` : ""}
              {job.remote_type ? ` · ${job.remote_type}` : ""}
              {salary ? ` · ${salary}` : ""}
            </p>

            {boardCount > 1 && (
              <p className="mt-1 text-sm font-medium text-cyan-200">
                Found on {boardCount} job boards
              </p>
            )}

            {actionFeedback && (
              <p role="status" aria-live="polite" className="mt-1 text-xs text-emerald-300">
                {actionFeedback}
              </p>
            )}

            {actionError && (
              <p role="alert" className="mt-1 text-xs text-rose-300">
                {actionError}
              </p>
            )}

            <button
              type="button"
              onClick={() => {
                setExpanded((current) => {
                  const next = !current;
                  if (next) void meApi.recordView(job.id);
                  return next;
                });
              }}
              aria-expanded={expanded}
              className="mt-3 rounded text-sm font-medium text-cyan-300 outline-none ring-cyan-300 transition hover:text-cyan-200 focus-visible:ring-2"
            >
              {expanded ? "Show less" : "Show more"}
            </button>

            {expanded && (
              <div className="mt-3">
                <p className="text-sm text-slate-400">
                  {job.listing_classification}
                  {job.repost_count > 0 ? ` · repost #${job.repost_count}` : ""}
                  {` · ${ageSummary(job)}`}
                  {postedOn ? ` · posted ${postedOn}` : ""}
                  {job.applicant_count != null
                    ? ` · ${job.applicant_count} reported applicants`
                    : ""}
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
              </div>
            )}
          </div>
        </div>

        <ScoreReasoningTooltip job={job} />
      </div>
    </article>
  );
}
