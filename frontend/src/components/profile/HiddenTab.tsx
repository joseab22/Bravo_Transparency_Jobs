import { useCallback, useState } from "react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { TabEmpty, TabError, TabLoading } from "@/components/profile/TabStates";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";
import { COMPACT_TITLE } from "@/lib/typography";
import { CARD } from "@/lib/designSystem";
import type { DismissalEntry } from "@/types/jobs";

export function HiddenTab() {
  const fetcher = useCallback(() => meApi.listHidden(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);

  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} />;
  if (items.length === 0) {
    return <TabEmpty message="Listings you hide from search results will show up here." />;
  }

  return (
    <div className="grid gap-3">
      {items.map((entry) => (
        <HiddenRow
          key={entry.job_posting_id}
          entry={entry}
          onRestored={() =>
            setItems((current) => current.filter((item) => item.job_posting_id !== entry.job_posting_id))
          }
        />
      ))}
    </div>
  );
}

function HiddenRow({ entry, onRestored }: { entry: DismissalEntry; onRestored: () => void }) {
  const [restoring, setRestoring] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [noteOpen, setNoteOpen] = useState(false);
  const [savedNote, setSavedNote] = useState(entry.job.note ?? "");
  const [noteText, setNoteText] = useState(entry.job.note ?? "");
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [noteFeedback, setNoteFeedback] = useState<string | null>(null);

  const noteDirty = noteText !== savedNote;

  async function restore() {
    setRestoring(true);
    setErrorMessage(null);
    try {
      await meApi.undismissJob(entry.job_posting_id);
      onRestored();
    } catch {
      setErrorMessage("Could not unhide this listing. Try again.");
      setRestoring(false);
    }
  }

  async function saveNote() {
    setNoteSaving(true);
    setNoteError(null);
    setNoteFeedback(null);
    try {
      const trimmed = noteText.trim();
      if (trimmed) {
        await meApi.upsertNote(entry.job_posting_id, trimmed);
      } else {
        await meApi.removeNote(entry.job_posting_id);
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

  return (
    <div className={`${CARD} p-4`}>
      <div className="flex items-center gap-3">
        <CompanyLogo name={entry.job.company.name} logoUrl={entry.job.company.logo_url} size={32} />

        <div className="min-w-0 flex-1">
          <h2 className={`truncate ${COMPACT_TITLE}`}>{entry.job.title_raw}</h2>
          <p className="truncate text-sm text-slate-400">{entry.job.company.name}</p>
        </div>

        {errorMessage && (
          <span role="alert" className="text-xs text-rose-300">
            {errorMessage}
          </span>
        )}

        <button
          type="button"
          onClick={() => setNoteOpen((open) => !open)}
          className="shrink-0 rounded-lg border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-300 outline-none ring-cyan-300 transition hover:border-cyan-300 hover:text-cyan-200 focus-visible:ring-2"
        >
          {savedNote ? "Edit note" : "Add note"}
        </button>

        <button
          type="button"
          onClick={restore}
          disabled={restoring}
          className="shrink-0 rounded-lg border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-300 outline-none ring-cyan-300 transition hover:border-cyan-300 hover:text-cyan-200 focus-visible:ring-2 disabled:opacity-50"
        >
          Unhide
        </button>
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
    </div>
  );
}
