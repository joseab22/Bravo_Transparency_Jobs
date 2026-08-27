import { useCallback } from "react";

import { JobCard } from "@/components/JobCard";
import { TabEmpty, TabError, TabLoading } from "@/components/profile/TabStates";
import { meApi } from "@/lib/api";
import { useAsyncList } from "@/lib/useAsyncList";

export function FavoritesTab() {
  const fetcher = useCallback(() => meApi.listFavorites(), []);
  const { items, setItems, loading, error } = useAsyncList(fetcher);

  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} />;
  if (items.length === 0) {
    return (
      <TabEmpty message="You haven't saved any jobs yet. Use the star on a listing to save it here." />
    );
  }

  return (
    <div className="grid gap-4">
      {items.map((entry) => (
        <JobCard
          key={entry.job_posting_id}
          job={entry.job}
          onFavoriteChange={(jobId, favorited) => {
            if (!favorited) {
              setItems((current) => current.filter((item) => item.job_posting_id !== jobId));
            }
          }}
        />
      ))}
    </div>
  );
}
