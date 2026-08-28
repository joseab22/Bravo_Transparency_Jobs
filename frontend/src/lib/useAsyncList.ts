import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

interface AsyncListResult<T> {
  items: T[];
  setItems: Dispatch<SetStateAction<T[]>>;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useAsyncList<T>(fetcher: () => Promise<T[]>): AsyncListResult<T> {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetcher());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load.");
    } finally {
      setLoading(false);
    }
    // fetcher is expected to be stable (wrapped in useCallback by the caller).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, setItems, loading, error, reload };
}
