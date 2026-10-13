import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect, useRef, useState } from "react";

import { FilterPanel } from "@/components/FilterPanel";
import {
  AdvancedFilterFields,
  DEFAULT_FILTER_VALUES,
  PrimaryFilterFields,
  type FilterKey,
  type FilterValues,
} from "@/components/FilterFields";
import { JobCard } from "@/components/JobCard";
import { JobDetailPanel } from "@/components/JobDetailPanel";
import { JobListRow } from "@/components/JobListRow";
import { SavedSearchesSection } from "@/components/SavedSearchesSection";
import { jobsApi } from "@/lib/api";
import { SITE_URL } from "@/lib/seo";
import { HERO_TITLE } from "@/lib/typography";
import { CARD } from "@/lib/designSystem";
import type { JobListItem } from "@/types/jobs";

const PAGE_SIZE = 50;

interface DatePostedOption {
  value: string;
  label: string;
  maxAgeDays: number | undefined;
}

const DATE_POSTED_OPTIONS: DatePostedOption[] = [
  { value: "3", label: "Last 3 days", maxAgeDays: 3 },
  { value: "7", label: "Last 7 days", maxAgeDays: 7 },
  { value: "14", label: "Last 14 days", maxAgeDays: 14 },
  { value: "21", label: "Last 21 days", maxAgeDays: 21 },
  { value: "any", label: "30+ days (no limit)", maxAgeDays: undefined },
];
const DEFAULT_DATE_POSTED = "any";

function resolveDatePosted(value: string): DatePostedOption {
  return DATE_POSTED_OPTIONS.find((option) => option.value === value) ?? DATE_POSTED_OPTIONS[3];
}

// Saved searches created before this filter existed stored a boolean
// includeOlderJobs flag instead. Map it onto the closest equivalent bucket
// so old saved searches keep working rather than silently resetting.
function resolveDatePostedFromPayload(payload: { datePostedWithin?: string; includeOlderJobs?: boolean }): string {
  if (payload.datePostedWithin) return payload.datePostedWithin;
  if (typeof payload.includeOlderJobs === "boolean") {
    return payload.includeOlderJobs ? "any" : DEFAULT_DATE_POSTED;
  }
  return DEFAULT_DATE_POSTED;
}

export default function Home() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState<FilterValues>(DEFAULT_FILTER_VALUES);
  const [collapseCanonical, setCollapseCanonical] = useState(true);
  const [showMissingDescription, setShowMissingDescription] = useState(false);
  const [datePostedWithin, setDatePostedWithin] = useState(DEFAULT_DATE_POSTED);
  const [filtersPanelOpen, setFiltersPanelOpen] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  // "split": compact rows + a sticky detail panel (default). "cards": fuller
  // self-contained cards in a single column, no separate detail panel --
  // each card already has everything (description, Found on, notes) inline.
  const [viewMode, setViewMode] = useState<"split" | "cards">("split");
  const didInitSelectionFromUrl = useRef(false);
  const isInitialLoad = useRef(true);

  // Restore a shared link (/?job=123) once the router has the real query
  // available (router.query is empty on the very first client render).
  useEffect(() => {
    if (!router.isReady || didInitSelectionFromUrl.current) return;
    didInitSelectionFromUrl.current = true;
    const queryJob = router.query.job;
    const parsed = typeof queryJob === "string" ? Number(queryJob) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) setSelectedJobId(parsed);
  }, [router.isReady, router.query.job]);

  // Selecting a job updates the URL to /?job=123 so the link is shareable
  // and back/forward moves between selections -- via shallow routing, which
  // only works for a query-string change on this same page (Next.js can't
  // shallow-route to a literal different path like /jobs/123 while staying
  // mounted on this page's component). A separate, genuinely standalone
  // page lives at /jobs/[id] for direct visits and crawlers.
  function selectJob(jobId: number | null, options: { push?: boolean } = {}) {
    setSelectedJobId(jobId);
    const nextQuery: Record<string, string> = {};
    Object.entries(router.query).forEach(([key, value]) => {
      if (typeof value === "string") nextQuery[key] = value;
    });
    if (jobId == null) {
      delete nextQuery.job;
    } else {
      nextQuery.job = String(jobId);
    }
    const method = options.push ? router.push : router.replace;
    void method.call(router, { pathname: "/", query: nextQuery }, undefined, { shallow: true });
  }

  function syncFavorite(jobId: number, favorited: boolean) {
    setJobs((current) => current.map((item) => (item.id === jobId ? { ...item, is_favorited: favorited } : item)));
  }

  function syncApplied(jobId: number, applied: boolean) {
    setJobs((current) => current.map((item) => (item.id === jobId ? { ...item, is_applied: applied } : item)));
  }

  function handleDismissed(jobId: number) {
    setJobs((current) => current.filter((item) => item.id !== jobId));
    if (selectedJobId === jobId) {
      const remaining = jobs.filter((item) => item.id !== jobId);
      selectJob(remaining[0]?.id ?? null);
    }
  }

  function updateFilter<K extends FilterKey>(key: K, value: FilterValues[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTER_VALUES);
    setDatePostedWithin(DEFAULT_DATE_POSTED);
    setShowMissingDescription(false);
    void load(1, false, {
      filters: DEFAULT_FILTER_VALUES,
      datePostedWithin: DEFAULT_DATE_POSTED,
      showMissingDescription: false,
    });
  }

  function renderToggles() {
    return (
      <>
        <label className="flex items-center gap-2 text-sm text-ink-secondary">
          <input
            type="checkbox"
            checked={collapseCanonical}
            onChange={(event) => {
              const nextValue = event.target.checked;
              setCollapseCanonical(nextValue);
              void load(1, false, { collapseCanonical: nextValue });
            }}
            className="h-4 w-4"
          />
          Collapse related listings
        </label>

        <label className="flex items-center gap-2 text-sm text-ink-secondary">
          <input
            type="checkbox"
            checked={showMissingDescription}
            onChange={(event) => {
              const nextValue = event.target.checked;
              setShowMissingDescription(nextValue);
              void load(1, false, { showMissingDescription: nextValue });
            }}
            className="h-4 w-4"
          />
          Show jobs without a description
        </label>

        <label className="flex items-center gap-2 text-sm text-ink-secondary">
          <span>Date posted</span>
          <select
            aria-label="Date posted"
            value={datePostedWithin}
            onChange={(event) => {
              const nextValue = event.target.value;
              setDatePostedWithin(nextValue);
              void load(1, false, { datePostedWithin: nextValue });
            }}
            className="rounded-lg border border-line bg-page px-3 py-1.5 text-ink-primary outline-none ring-accent focus-visible:ring-2"
          >
            {DATE_POSTED_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </>
    );
  }

  async function load(
    targetPage = 1,
    scrollAfterLoad = false,
    overrides?: {
      collapseCanonical?: boolean;
      showMissingDescription?: boolean;
      datePostedWithin?: string;
      filters?: FilterValues;
    },
  ) {
    if (targetPage < 1) return;

    setLoading(true);
    setError(null);

    try {
      const activeFilters = overrides?.filters ?? filters;
      const data = await jobsApi.list({
        page: targetPage,
        page_size: PAGE_SIZE,
        q: activeFilters.q || undefined,
        job_family: activeFilters.jobFamily || undefined,
        job_board: activeFilters.jobBoard || undefined,
        applicant_max: activeFilters.applicantMax ? Number(activeFilters.applicantMax) : undefined,
        max_age_days: resolveDatePosted(overrides?.datePostedWithin ?? datePostedWithin).maxAgeDays,
        seniority: activeFilters.seniority || undefined,
        employment_type: activeFilters.employmentType || undefined,
        remote_type: activeFilters.remoteType || undefined,
        metro_area: activeFilters.metroArea || undefined,
        classification: activeFilters.classification || undefined,
        clearance_required:
          activeFilters.clearanceRequired === "" ? undefined : activeFilters.clearanceRequired === "true",
        salary_min: activeFilters.salaryMin ? Number(activeFilters.salaryMin) : undefined,
        salary_max: activeFilters.salaryMax ? Number(activeFilters.salaryMax) : undefined,
        active_hiring_min: activeFilters.activeHiringMin ? Number(activeFilters.activeHiringMin) : undefined,
        collapse_canonical: overrides?.collapseCanonical ?? collapseCanonical,
        show_missing_description: overrides?.showMissingDescription ?? showMissingDescription,
        sort_by: activeFilters.sortBy,
        sort_dir: activeFilters.sortDir,
      });

      setJobs(data.results);
      setTotalResults(data.total);
      setTotalPages(data.pages);
      setPage(data.page);
      // On the very first load, a shared link's ?job=123 (already applied by
      // the URL-hydration effect above, which runs synchronously on mount
      // before this fetch can resolve) takes precedence over auto-selecting
      // the first result -- every load after that behaves as before.
      if (isInitialLoad.current) {
        isInitialLoad.current = false;
        const queryJob = router.query.job;
        const parsedJobId = typeof queryJob === "string" ? Number(queryJob) : NaN;
        if (!(Number.isFinite(parsedJobId) && parsedJobId > 0)) {
          selectJob(data.results[0]?.id ?? null);
        }
      } else {
        selectJob(data.results[0]?.id ?? null);
      }

      if (scrollAfterLoad) {
        window.requestAnimationFrame(() => {
          window.scrollTo({
            top: 0,
            behavior: "smooth",
          });
        });
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load jobs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(1);
    // Initial load only; filter changes are applied when the search form is submitted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedDatePosted = resolveDatePosted(datePostedWithin);
  const firstVisibleResult = totalResults && jobs.length > 0 ? (page - 1) * PAGE_SIZE + 1 : 0;
  const lastVisibleResult = totalResults
    ? Math.min((page - 1) * PAGE_SIZE + jobs.length, totalResults)
    : 0;

  return (
    <>
      <Head>
        <title>JobLens | Active Hiring Confidence</title>
        <meta
          name="description"
          content="Posting history and active hiring signals for technology roles."
        />
        <link rel="canonical" href={`${SITE_URL}/`} />
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "JobLens",
              url: SITE_URL,
              description: "Posting history and active hiring signals for technology roles.",
            }),
          }}
        />
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <h1 className={HERO_TITLE}>Find jobs more likely to be actively hiring.</h1>

        <p className="mt-6 max-w-3xl text-lg leading-8 text-ink-secondary">
          Active Hiring Confidence uses posting age, repeated observations, parallel openings,
          repost history, compensation, and applicant signals. It is an estimate, not a guarantee
          of employer intent. This tool is intended as a supplement to your research and judgment,
          not a replacement for it. Always verify the information and use your own discretion when
          applying for jobs.
        </p>

        <p className="mt-3 text-ink-muted">
          Active Hiring Confidence (Ghost Job Filtering) · Repost tracking · Salary transparency
        </p>

        <form
          className={`mt-8 ${CARD} p-4`}
          onSubmit={(event) => {
            event.preventDefault();
            void load(1);
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <PrimaryFilterFields values={filters} onChange={updateFilter} />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
            {renderToggles()}
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-accent-solid px-5 py-3 font-semibold text-ink-onaccent disabled:opacity-60"
            >
              {loading ? "Loading…" : "Search jobs"}
            </button>

            <button
              type="button"
              onClick={() => setFiltersPanelOpen(true)}
              className="rounded-lg border border-line px-5 py-3 font-semibold text-ink-secondary outline-none ring-accent transition hover:border-accent hover:text-accent focus-visible:ring-2"
            >
              More filters
            </button>

            <button
              type="button"
              onClick={clearFilters}
              className="rounded-lg px-5 py-3 font-semibold text-ink-muted outline-none ring-accent transition hover:text-ink-secondary focus-visible:ring-2"
            >
              Clear filters
            </button>
          </div>
        </form>

        <FilterPanel open={filtersPanelOpen} onClose={() => setFiltersPanelOpen(false)}>
          <PrimaryFilterFields values={filters} onChange={updateFilter} />
          <div className="border-t border-line-subtle pt-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              More filters
            </p>
            <div className="flex flex-col gap-4">
              <AdvancedFilterFields values={filters} onChange={updateFilter} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-line-subtle pt-4">
            {renderToggles()}
          </div>
          <div className="mt-2 flex flex-wrap gap-3 border-t border-line-subtle pt-4">
            <button
              type="button"
              onClick={() => {
                setFiltersPanelOpen(false);
                void load(1);
              }}
              className="rounded-lg bg-accent-solid px-5 py-3 font-semibold text-ink-onaccent"
            >
              Apply filters
            </button>

            <button
              type="button"
              onClick={clearFilters}
              className="rounded-lg px-5 py-3 font-semibold text-ink-muted outline-none ring-accent transition hover:text-ink-secondary focus-visible:ring-2"
            >
              Clear filters
            </button>
          </div>

          <SavedSearchesSection
            currentFilters={filters}
            collapseCanonical={collapseCanonical}
            datePostedWithin={datePostedWithin}
            onApply={(payload) => {
              const nextDatePosted = resolveDatePostedFromPayload(payload);
              setFilters(payload.filters);
              setCollapseCanonical(payload.collapseCanonical);
              setDatePostedWithin(nextDatePosted);
              setFiltersPanelOpen(false);
              void load(1, false, {
                filters: payload.filters,
                collapseCanonical: payload.collapseCanonical,
                datePostedWithin: nextDatePosted,
              });
            }}
          />
        </FilterPanel>

        {error && error.includes("waking up") && (
          <div
            role="status"
            className="mt-4 flex items-start gap-3 rounded-lg border-2 border-warning bg-warning/15 p-4 text-ink-primary"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0 text-warning">
              <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path d="M12 7.5v5l3.5 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="font-semibold">{error}</p>
          </div>
        )}

        {error && !error.includes("waking up") && (
          <p className="mt-4 rounded-lg border border-negative/40 bg-negative/10 p-4 text-negative">
            {error}
          </p>
        )}

        {!loading && !error && totalResults !== null && (
          <div
            className="mt-8 rounded-lg border border-line bg-surface p-4 text-sm text-ink-secondary"
            role="status"
            aria-live="polite"
          >
            {totalResults > 0 ? (
              <p>
                Showing {firstVisibleResult}–{lastVisibleResult} of {totalResults} result
                {totalResults === 1 ? "" : "s"}. Page {page} of {Math.max(totalPages, 1)}.
                {collapseCanonical
                  ? " Related listings are grouped."
                  : " Each active listing is shown separately."}
                {selectedDatePosted.maxAgeDays
                  ? ` Listings posted more than ${selectedDatePosted.maxAgeDays} days ago are hidden.`
                  : " Listings of any age are included."}
              </p>
            ) : (
              <p>No results found for these filters.</p>
            )}
          </div>
        )}

        {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
          <nav
            aria-label="Top job results pagination"
            className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-line bg-surface p-3"
          >
            <button
              type="button"
              onClick={() => load(page - 1, true)}
              disabled={page <= 1 || loading}
              className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-secondary transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>

            <p className="text-sm text-ink-muted">
              Page {page} of {totalPages}
            </p>

            <button
              type="button"
              onClick={() => load(page + 1, true)}
              disabled={page >= totalPages || loading}
              className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-secondary transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </nav>
        )}

        {loading && jobs.length === 0 && (
          <>
            <p className="mt-10 text-center text-sm text-ink-muted">
              Loading jobs… This can take up to a minute on the first visit in a while, while the
              server wakes up. If it does not finish, try refreshing the page.
            </p>
            <div className="mt-4 grid gap-4" aria-label="Loading jobs">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={index}
                  className={`h-36 animate-pulse ${CARD}`}
                />
              ))}
            </div>
          </>
        )}

        {!loading && !error && totalResults === 0 && (
          <div className={`mt-10 ${CARD} flex flex-col items-center gap-3 p-8 text-center`}>
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-10 w-10 text-ink-faint">
              <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <line x1="15.3" y1="15.3" x2="20.5" y2="20.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              <line x1="7.5" y1="10.5" x2="13.5" y2="10.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <p className="font-semibold text-ink-secondary">No jobs match these filters.</p>
            <p className="max-w-sm text-sm text-ink-muted">
              Try clearing one or more filters, increasing the max reported applicants value, or
              searching a broader city, state, title, or company.
            </p>
            <button
              type="button"
              onClick={clearFilters}
              className="mt-1 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-secondary outline-none ring-accent transition hover:border-accent hover:text-accent focus-visible:ring-2"
            >
              Clear all filters
            </button>
          </div>
        )}

        {!loading && !error && jobs.length > 0 && (
          <div className="mt-6 flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink-faint">View</span>
            <div className="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group" aria-label="Results view">
              <button
                type="button"
                onClick={() => setViewMode("split")}
                aria-pressed={viewMode === "split"}
                className={`rounded-md px-3 py-1.5 text-sm font-medium outline-none ring-accent transition focus-visible:ring-2 ${
                  viewMode === "split" ? "bg-accent-solid text-ink-onaccent" : "text-ink-secondary hover:text-ink-primary"
                }`}
              >
                Split view
              </button>
              <button
                type="button"
                onClick={() => setViewMode("cards")}
                aria-pressed={viewMode === "cards"}
                className={`rounded-md px-3 py-1.5 text-sm font-medium outline-none ring-accent transition focus-visible:ring-2 ${
                  viewMode === "cards" ? "bg-accent-solid text-ink-onaccent" : "text-ink-secondary hover:text-ink-primary"
                }`}
              >
                Card view
              </button>
            </div>
          </div>
        )}

        {viewMode === "split" ? (
          <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="flex flex-col gap-4">
              {jobs.map((job) => (
                <JobListRow
                  key={job.id}
                  job={job}
                  selected={job.id === selectedJobId}
                  onSelect={() => selectJob(job.id, { push: true })}
                  onDismissed={handleDismissed}
                  onFavoriteChange={syncFavorite}
                  onAppliedChange={syncApplied}
                />
              ))}
            </div>

            {jobs.length > 0 && (
              <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
                <JobDetailPanel
                  jobId={selectedJobId}
                  fallback={jobs.find((job) => job.id === selectedJobId) ?? null}
                  maxAgeDays={selectedDatePosted.maxAgeDays}
                  onDismissed={handleDismissed}
                  onFavoriteChange={syncFavorite}
                  onAppliedChange={syncApplied}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="mt-4 grid gap-4">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onDismissed={handleDismissed}
                onFavoriteChange={syncFavorite}
                onAppliedChange={syncApplied}
              />
            ))}
          </div>
        )}

        {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
          <nav
            aria-label="Job results pagination"
            className="mt-8 flex items-center justify-between gap-4"
          >
            <button
              type="button"
              onClick={() => load(page - 1, true)}
              disabled={page <= 1 || loading}
              className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-secondary transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>

            <p className="text-sm text-ink-muted">
              Page {page} of {totalPages}
            </p>

            <button
              type="button"
              onClick={() => load(page + 1, true)}
              disabled={page >= totalPages || loading}
              className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-semibold text-ink-secondary transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </nav>
        )}
      </section>
    </>
  );
}