import { useCallback, useState } from "react";

import type { FilterValues } from "@/components/FilterFields";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";

export interface SavedSearchPayload {
  filters: FilterValues;
  collapseCanonical: boolean;
  datePostedWithin: string;
}

interface SavedSearchesSectionProps {
  currentFilters: FilterValues;
  collapseCanonical: boolean;
  datePostedWithin: string;
  onApply: (payload: SavedSearchPayload) => void;
}

export function SavedSearchesSection({
  currentFilters,
  collapseCanonical,
  datePostedWithin,
  onApply,
}: SavedSearchesSectionProps) {
  const fetcher = useCallback(() => meApi.listSavedSearches(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function save() {
    const trimmed = name.trim();
    if (!trimmed) return;

    setSaving(true);
    setActionError(null);
    try {
      const payload: SavedSearchPayload = { filters: currentFilters, collapseCanonical, datePostedWithin };
      const saved = await meApi.saveSearch(trimmed, payload as unknown as Record<string, unknown>);
      setItems((current) => [saved, ...current.filter((item) => item.name !== saved.name)]);
      setName("");
    } catch {
      setActionError("Could not save this search. Try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    setActionError(null);
    try {
      await meApi.removeSavedSearch(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch {
      setActionError("Could not remove this saved search. Try again.");
    }
  }

  return (
    <div className="border-t border-line-subtle pt-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">
        Saved searches
      </p>

      {loading && <p className="text-sm text-ink-faint">Loading saved searches…</p>}
      {error && (
        <p role="alert" className="text-sm text-negative">
          {error}
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-ink-faint">No saved searches yet.</p>
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-line-subtle px-3 py-2"
            >
              <button
                type="button"
                onClick={() => onApply(entry.filters as unknown as SavedSearchPayload)}
                className="min-w-0 flex-1 truncate rounded text-left text-sm font-medium text-ink-secondary outline-none ring-accent hover:text-accent focus-visible:ring-2"
              >
                {entry.name}
              </button>
              <button
                type="button"
                onClick={() => remove(entry.id)}
                aria-label={`Delete saved search ${entry.name}`}
                className="shrink-0 rounded text-xs text-ink-faint outline-none ring-accent hover:text-negative focus-visible:ring-2"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex gap-2">
        <input
          aria-label="New saved search name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Name this search"
          className="min-w-0 flex-1 rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink-primary placeholder:text-ink-faint"
        />
        <button
          type="button"
          onClick={save}
          disabled={saving || !name.trim()}
          className="shrink-0 rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink-secondary outline-none ring-accent transition hover:border-accent hover:text-accent focus-visible:ring-2 disabled:opacity-50"
        >
          Save current
        </button>
      </div>

      {actionError && (
        <p role="alert" className="mt-2 text-sm text-negative">
          {actionError}
        </p>
      )}
    </div>
  );
}
