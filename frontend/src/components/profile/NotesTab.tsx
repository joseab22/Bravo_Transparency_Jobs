import { useCallback, useState } from "react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { TabEmpty, TabError, TabLoading } from "@/components/profile/TabStates";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";
import { COMPACT_TITLE } from "@/lib/typography";
import type { NoteEntry } from "@/types/jobs";

export function NotesTab() {
  const fetcher = useCallback(() => meApi.listNotes(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);

  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} />;
  if (items.length === 0) {
    return <TabEmpty message="Add a note to any listing to keep it here for later." />;
  }

  return (
    <div className="grid gap-4">
      {items.map((entry) => (
        <NoteRow
          key={entry.job_posting_id}
          entry={entry}
          onRemoved={() =>
            setItems((current) => current.filter((item) => item.job_posting_id !== entry.job_posting_id))
          }
          onUpdated={(updated) =>
            setItems((current) =>
              current.map((item) => (item.job_posting_id === updated.job_posting_id ? updated : item)),
            )
          }
        />
      ))}
    </div>
  );
}

function NoteRow({
  entry,
  onRemoved,
  onUpdated,
}: {
  entry: NoteEntry;
  onRemoved: () => void;
  onUpdated: (entry: NoteEntry) => void;
}) {
  const [note, setNote] = useState(entry.note ?? "");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dirty = note !== (entry.note ?? "");
  const hasStandaloneNote = Boolean(entry.note);

  async function save() {
    setSaving(true);
    setErrorMessage(null);
    setFeedback(null);
    const trimmed = note.trim();
    try {
      if (trimmed) {
        const updated = await meApi.upsertNote(entry.job_posting_id, trimmed);
        setNote(trimmed);
        onUpdated({ ...updated, application_note: entry.application_note });
        setFeedback("Saved.");
      } else if (entry.application_note) {
        await meApi.removeNote(entry.job_posting_id);
        onUpdated({ ...entry, note: null });
        setFeedback("Note removed.");
      } else {
        await meApi.removeNote(entry.job_posting_id);
        onRemoved();
      }
    } catch {
      setErrorMessage("Could not save this note. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setRemoving(true);
    setErrorMessage(null);
    try {
      await meApi.removeNote(entry.job_posting_id);
      // A job with an application note stays in this list even after its
      // standalone note is deleted -- it's still "a job with a note", just
      // one now sourced only from the Applications tab.
      if (entry.application_note) {
        setNote("");
        onUpdated({ ...entry, note: null });
      } else {
        onRemoved();
      }
    } catch {
      setErrorMessage("Could not remove this note. Try again.");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start gap-3">
        <CompanyLogo name={entry.job.company.name} logoUrl={entry.job.company.logo_url} />

        <div className="min-w-0 flex-1">
          <h2 className={COMPACT_TITLE}>{entry.job.title_raw}</h2>
          <p className="mt-1 text-sm text-slate-300">{entry.job.company.name}</p>
        </div>

        {hasStandaloneNote && (
          <button
            type="button"
            onClick={remove}
            disabled={removing}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 outline-none ring-cyan-300 transition hover:border-rose-400 hover:text-rose-300 focus-visible:ring-2 disabled:opacity-50"
          >
            {removing ? "Removing…" : "Delete"}
          </button>
        )}
      </div>

      <label className="mt-3 block text-sm text-slate-300">
        Note
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={3}
          placeholder="Add a personal note about this listing..."
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
        />
      </label>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save note"}
        </button>
        {feedback && <span className="text-sm text-emerald-300">{feedback}</span>}
        {errorMessage && (
          <span role="alert" className="text-sm text-rose-300">
            {errorMessage}
          </span>
        )}
      </div>

      {entry.application_note && (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Application note
          </p>
          <p className="mt-1 whitespace-pre-line text-sm text-slate-300">{entry.application_note}</p>
          <p className="mt-1.5 text-xs text-slate-500">Edit this from the Applications tab.</p>
        </div>
      )}
    </div>
  );
}
