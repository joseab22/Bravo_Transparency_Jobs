import { useCallback, useState } from "react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { TabEmpty, TabError, TabLoading } from "@/components/profile/TabStates";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";
import { COMPACT_TITLE } from "@/lib/typography";
import { CARD } from "@/lib/designSystem";
import type { ApplicationEntry, ApplicationStatus } from "@/types/jobs";

const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

export function ApplicationsTab() {
  const fetcher = useCallback(() => meApi.listApplications(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);

  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} />;
  if (items.length === 0) {
    return (
      <TabEmpty message="Jobs you mark as applied will show up here, with status and notes you can edit." />
    );
  }

  return (
    <div className="grid gap-4">
      {items.map((entry) => (
        <ApplicationRow
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

function toDateInputValue(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString().slice(0, 10);
}

function ApplicationRow({
  entry,
  onRemoved,
  onUpdated,
}: {
  entry: ApplicationEntry;
  onRemoved: () => void;
  onUpdated: (entry: ApplicationEntry) => void;
}) {
  const [status, setStatus] = useState<ApplicationStatus>(entry.status);
  const [appliedDate, setAppliedDate] = useState(toDateInputValue(entry.applied_date));
  const [notes, setNotes] = useState(entry.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const dirty =
    status !== entry.status ||
    appliedDate !== toDateInputValue(entry.applied_date) ||
    notes !== (entry.notes ?? "");

  async function save() {
    setSaving(true);
    setErrorMessage(null);
    setFeedback(null);
    try {
      const updated = await meApi.upsertApplication(entry.job_posting_id, {
        status,
        applied_date: appliedDate ? new Date(appliedDate).toISOString() : null,
        notes: notes || null,
      });
      onUpdated(updated);
      setFeedback("Saved.");
    } catch {
      setErrorMessage("Could not save changes. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setRemoving(true);
    setErrorMessage(null);
    try {
      await meApi.removeApplication(entry.job_posting_id);
      onRemoved();
    } catch {
      setErrorMessage("Could not remove this application. Try again.");
      setRemoving(false);
    }
  }

  return (
    <div className={`${CARD} p-5`}>
      <div className="flex items-start gap-3">
        <CompanyLogo name={entry.job.company.name} logoUrl={entry.job.company.logo_url} />

        <div className="min-w-0 flex-1">
          <h2 className={COMPACT_TITLE}>{entry.job.title_raw}</h2>
          <p className="mt-1 text-sm text-slate-300">{entry.job.company.name}</p>
        </div>

        <button
          type="button"
          onClick={remove}
          disabled={removing}
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 outline-none ring-cyan-300 transition hover:border-rose-400 hover:text-rose-300 focus-visible:ring-2 disabled:opacity-50"
        >
          Remove
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-slate-300">
          Status
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as ApplicationStatus)}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-slate-300">
          Application date
          <input
            type="date"
            value={appliedDate}
            onChange={(event) => setAppliedDate(event.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
          />
        </label>
      </div>

      <label className="mt-3 block text-sm text-slate-300">
        Notes
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={3}
          placeholder="Interview rounds, contacts, follow-ups..."
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
          {saving ? "Saving…" : "Save changes"}
        </button>
        {feedback && <span className="text-sm text-emerald-300">{feedback}</span>}
        {errorMessage && (
          <span role="alert" className="text-sm text-rose-300">
            {errorMessage}
          </span>
        )}
      </div>
    </div>
  );
}
