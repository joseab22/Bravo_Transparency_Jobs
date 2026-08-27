import { useCallback, useState } from "react";

import { JobCard } from "@/components/JobCard";
import { TabEmpty, TabError, TabLoading } from "@/components/profile/TabStates";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";

export function RecentTab() {
  const fetcher = useCallback(() => meApi.listRecentlyViewed(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);
  const [confirming, setConfirming] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} />;
  if (items.length === 0) {
    return <TabEmpty message="Jobs you open from search results will show up here." />;
  }

  async function clearAll() {
    setClearing(true);
    setClearError(null);
    try {
      await meApi.clearRecentlyViewed();
      setItems([]);
      setConfirming(false);
    } catch {
      setClearError("Could not clear recently viewed jobs. Try again.");
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-end gap-3">
        {clearError && (
          <span role="alert" className="text-sm text-rose-300">
            {clearError}
          </span>
        )}
        {confirming ? (
          <>
            <span className="text-sm text-slate-400">Clear all {items.length} entries?</span>
            <button
              type="button"
              onClick={clearAll}
              disabled={clearing}
              className="rounded-lg border border-rose-500/50 px-3 py-1.5 text-sm font-semibold text-rose-300 outline-none ring-cyan-300 transition hover:bg-rose-950/30 focus-visible:ring-2 disabled:opacity-50"
            >
              {clearing ? "Clearing…" : "Confirm clear"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={clearing}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-400 outline-none ring-cyan-300 transition hover:text-slate-200 focus-visible:ring-2 disabled:opacity-50"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-300 outline-none ring-cyan-300 transition hover:border-rose-400 hover:text-rose-300 focus-visible:ring-2"
          >
            Clear all
          </button>
        )}
      </div>

      {items.map((entry) => (
        <JobCard
          key={entry.job_posting_id}
          job={entry.job}
          onDismissed={(jobId) =>
            setItems((current) => current.filter((item) => item.job_posting_id !== jobId))
          }
        />
      ))}
    </div>
  );
}
