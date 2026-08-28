import { useEffect, useRef, useState } from "react";

import { meApi } from "@/lib/api";
import type { JobListItem } from "@/types/jobs";

interface UseJobActionsOptions {
  onFavoriteChange?: (jobId: number, favorited: boolean) => void;
  onAppliedChange?: (jobId: number, applied: boolean) => void;
  onDismissed?: (jobId: number) => void;
}

export function useJobActions(job: JobListItem, options: UseJobActionsOptions = {}) {
  const { onFavoriteChange, onAppliedChange, onDismissed } = options;

  const [favorited, setFavorited] = useState(job.is_favorited);
  const [applied, setApplied] = useState(job.is_applied);
  const [favoritePending, setFavoritePending] = useState(false);
  const [appliedPending, setAppliedPending] = useState(false);
  const [dismissPending, setDismissPending] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const feedbackTimeoutRef = useRef<number | null>(null);

  // A single hook instance can be reused for a different job (e.g. a detail
  // panel that swaps which job it's showing) -- reset transient state
  // whenever the job identity itself changes, not just when its data is
  // refetched.
  useEffect(() => {
    setDismissed(false);
    setActionError(null);
    setActionFeedback(null);
  }, [job.id]);

  // The list row and the detail panel each hold their own instance of this
  // hook for the same job. Syncing on job.is_favorited/job.is_applied
  // directly (rather than only on job.id) means a toggle in one place is
  // reflected in the other once the parent's job list updates, instead of
  // the non-clicked instance keeping its stale initial value indefinitely.
  useEffect(() => {
    setFavorited(job.is_favorited);
  }, [job.is_favorited]);

  useEffect(() => {
    setApplied(job.is_applied);
  }, [job.is_applied]);

  useEffect(() => {
    return () => {
      if (feedbackTimeoutRef.current) window.clearTimeout(feedbackTimeoutRef.current);
    };
  }, []);

  function showFeedback(message: string) {
    setActionFeedback(message);
    if (feedbackTimeoutRef.current) window.clearTimeout(feedbackTimeoutRef.current);
    feedbackTimeoutRef.current = window.setTimeout(() => setActionFeedback(null), 2500);
  }

  async function toggleFavorite() {
    if (favoritePending) return;
    const next = !favorited;
    setFavoritePending(true);
    setActionError(null);
    setFavorited(next);
    try {
      if (next) {
        await meApi.addFavorite(job.id);
      } else {
        await meApi.removeFavorite(job.id);
      }
      onFavoriteChange?.(job.id, next);
      showFeedback(next ? "Added to favorites." : "Removed from favorites.");
    } catch {
      setFavorited(!next);
      setActionError("Could not update favorite. Try again.");
    } finally {
      setFavoritePending(false);
    }
  }

  async function toggleApplied() {
    if (appliedPending) return;
    const next = !applied;
    setAppliedPending(true);
    setActionError(null);
    setApplied(next);
    try {
      if (next) {
        await meApi.upsertApplication(job.id, {
          status: "applied",
          applied_date: new Date().toISOString(),
        });
      } else {
        await meApi.removeApplication(job.id);
      }
      onAppliedChange?.(job.id, next);
      showFeedback(next ? "Marked as applied." : "Application status removed.");
    } catch {
      setApplied(!next);
      setActionError("Could not update application status. Try again.");
    } finally {
      setAppliedPending(false);
    }
  }

  async function dismiss() {
    if (dismissPending) return;
    setDismissPending(true);
    setActionError(null);
    try {
      await meApi.dismissJob(job.id);
      setDismissed(true);
      onDismissed?.(job.id);
    } catch {
      setActionError("Could not hide this listing. Try again.");
      setDismissPending(false);
    }
  }

  return {
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
  };
}
