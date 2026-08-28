import { getDeviceId } from "@/lib/deviceId";
import type {
  ApplicationEntry,
  ApplicationInput,
  DismissalEntry,
  FavoriteEntry,
  JobDetail,
  JobFilters,
  MarketStats,
  NoteEntry,
  PaginatedJobs,
  RecentlyViewedEntry,
  SavedSearchEntry,
} from "@/types/jobs";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

function buildQuery(filters: JobFilters): string {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    params.set(key, String(value));
  });

  const query = params.toString();
  return query ? `?${query}` : "";
}

function deviceHeaders(extra?: Record<string, string>): Record<string, string> {
  const deviceId = getDeviceId();
  return {
    ...(deviceId ? { "X-Device-Id": deviceId } : {}),
    ...extra,
  };
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; parseJson?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, parseJson = true } = options;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30_000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      method,
      headers: deviceHeaders({
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      }),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Request to ${path} returned ${response.status}`);
    }

    if (!parseJson || response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The request timed out.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const jobsApi = {
  async list(filters: JobFilters = {}): Promise<PaginatedJobs> {
    return request<PaginatedJobs>(`/jobs${buildQuery(filters)}`);
  },
  async get(jobId: number, maxAgeDays?: number): Promise<JobDetail> {
    const query = maxAgeDays != null ? `?max_age_days=${maxAgeDays}` : "";
    return request<JobDetail>(`/jobs/${jobId}${query}`);
  },
  async stats(): Promise<MarketStats> {
    return request<MarketStats>("/jobs/stats");
  },
};

export const meApi = {
  listFavorites: () => request<FavoriteEntry[]>("/me/favorites"),
  addFavorite: (jobId: number) => request<FavoriteEntry>(`/me/favorites/${jobId}`, { method: "POST" }),
  removeFavorite: (jobId: number) =>
    request<void>(`/me/favorites/${jobId}`, { method: "DELETE", parseJson: false }),

  listApplications: () => request<ApplicationEntry[]>("/me/applications"),
  upsertApplication: (jobId: number, input: ApplicationInput) =>
    request<ApplicationEntry>(`/me/applications/${jobId}`, { method: "PUT", body: input }),
  removeApplication: (jobId: number) =>
    request<void>(`/me/applications/${jobId}`, { method: "DELETE", parseJson: false }),

  listNotes: () => request<NoteEntry[]>("/me/notes"),
  upsertNote: (jobId: number, note: string) =>
    request<NoteEntry>(`/me/notes/${jobId}`, { method: "PUT", body: { note } }),
  removeNote: (jobId: number) => request<void>(`/me/notes/${jobId}`, { method: "DELETE", parseJson: false }),

  recordView: (jobId: number) =>
    request<void>(`/me/views/${jobId}`, { method: "POST", parseJson: false }),
  listRecentlyViewed: () => request<RecentlyViewedEntry[]>("/me/recently-viewed"),
  clearRecentlyViewed: () =>
    request<void>("/me/recently-viewed", { method: "DELETE", parseJson: false }),

  listHidden: () => request<DismissalEntry[]>("/me/hidden"),
  dismissJob: (jobId: number) => request<void>(`/me/hidden/${jobId}`, { method: "POST", parseJson: false }),
  undismissJob: (jobId: number) =>
    request<void>(`/me/hidden/${jobId}`, { method: "DELETE", parseJson: false }),

  listSavedSearches: () => request<SavedSearchEntry[]>("/me/saved-searches"),
  saveSearch: (name: string, filters: Record<string, unknown>) =>
    request<SavedSearchEntry>("/me/saved-searches", { method: "POST", body: { name, filters } }),
  removeSavedSearch: (id: number) =>
    request<void>(`/me/saved-searches/${id}`, { method: "DELETE", parseJson: false }),
};
