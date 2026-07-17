import Head from "next/head";
import { useEffect, useState } from "react";

import { jobsApi } from "@/lib/api";
import type { JobListItem } from "@/types/jobs";

const PAGE_SIZE = 50;
const DEFAULT_MAX_AGE_DAYS = 30;
const MILLISECONDS_PER_DAY = 86_400_000;

function parseApiDate(value?: string | null): Date | null {
  if (!value) return null;

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function utcDayNumber(value?: string | null): number | null {
  const parsed = parseApiDate(value);
  if (!parsed) return null;

  return Math.floor(
    Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );
}

function daysAgo(value?: string | null): number | null {
  const day = utcDayNumber(value);
  if (day == null) return null;

  const now = new Date();
  const today = Math.floor(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) /
      MILLISECONDS_PER_DAY,
  );

  return Math.max(today - day, 0);
}

function daysBetween(start?: string | null, end?: string | null): number | null {
  const startDay = utcDayNumber(start);
  const endDay = utcDayNumber(end);
  if (startDay == null || endDay == null) return null;

  return Math.max(endDay - startDay, 0);
}

function dayLabel(value: number): string {
  return `${value} day${value === 1 ? "" : "s"}`;
}

function ageSummary(job: JobListItem): string {
  const postingAge = daysAgo(job.date_posted);
  const firstSeenAge = daysAgo(job.date_first_seen);
  const trackedDays = daysBetween(job.date_first_seen, job.date_last_seen);

  const postingText =
    postingAge == null
      ? firstSeenAge === 0
        ? "first observed today"
        : firstSeenAge == null
          ? "posting date unavailable"
          : `first observed ${dayLabel(firstSeenAge)} ago`
      : postingAge === 0
        ? "posted today"
        : `posted ${dayLabel(postingAge)} ago`;

  const trackingText =
    trackedDays == null
      ? null
      : trackedDays === 0
        ? "tracked today"
        : `tracked for ${dayLabel(trackedDays)}`;

  return trackingText ? `${postingText} · ${trackingText}` : postingText;
}

function confidenceLabel(value?: number | null): string {
  if (value == null) return "Not scored";
  if (value >= 70) return "Higher confidence";
  if (value >= 45) return "Mixed signals";
  return "Lower confidence";
}

function safeExternalUrl(value?: string | null): string | null {
  if (!value) return null;

  try {
    const parsed = new URL(value);

    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }

    if (parsed.username || parsed.password) {
      return null;
    }

    return parsed.toString();
  } catch {
    return null;
  }
}

function sourceLinks(job: JobListItem) {
  const sources = job.canonical_sources.length
    ? job.canonical_sources
    : [
        {
          sighting_key: `legacy-${job.id}-${job.source}`,
          source: job.source,
          publisher_name: job.publisher_name || job.source,
          source_url: job.source_url,
          collection_provider: job.collection_provider,
          external_id: null,
          is_direct: false,
          first_seen: job.date_first_seen,
          last_seen: job.date_last_seen,
          is_active: job.is_active,
          listing_ids: [job.id],
        },
      ];

  const totals = sources.reduce<Record<string, number>>((counts, source) => {
    counts[source.publisher_name] = (counts[source.publisher_name] || 0) + 1;
    return counts;
  }, {});

  const seen: Record<string, number> = {};

  return sources.map((source) => {
    seen[source.publisher_name] = (seen[source.publisher_name] || 0) + 1;

    const label =
      totals[source.publisher_name] > 1
        ? `${source.publisher_name} ${seen[source.publisher_name]}`
        : source.publisher_name;

    return { source, label };
  });
}

function formatSalary(job: JobListItem): string | null {
  if (!job.salary_listed || (job.salary_min == null && job.salary_max == null)) {
    return null;
  }

  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: job.salary_currency || "USD",
    maximumFractionDigits: 0,
  });

  if (job.salary_min != null && job.salary_max != null) {
    return `${formatter.format(job.salary_min)}–${formatter.format(job.salary_max)}`;
  }

  return formatter.format(job.salary_min ?? job.salary_max ?? 0);
}

export default function Home() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [jobFamily, setJobFamily] = useState("");
  const [jobBoard, setJobBoard] = useState("");
  const [applicantMax, setApplicantMax] = useState("");
  const [seniority, setSeniority] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [remoteType, setRemoteType] = useState("");
  const [classification, setClassification] = useState("");
  const [sortBy, setSortBy] = useState("active_hiring_confidence");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [collapseCanonical, setCollapseCanonical] = useState(true);
  const [includeOlderJobs, setIncludeOlderJobs] = useState(false);

  async function load(targetPage = 1, scrollAfterLoad = false) {
    if (targetPage < 1) return;

    setLoading(true);
    setError(null);

    try {
      const data = await jobsApi.list({
        page: targetPage,
        page_size: PAGE_SIZE,
        q: q || undefined,
        job_family: jobFamily || undefined,
        job_board: jobBoard || undefined,
        applicant_max: applicantMax ? Number(applicantMax) : undefined,
        max_age_days: includeOlderJobs ? undefined : DEFAULT_MAX_AGE_DAYS,
        seniority: seniority || undefined,
        employment_type: employmentType || undefined,
        remote_type: remoteType || undefined,
        classification: classification || undefined,
        collapse_canonical: collapseCanonical,
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      setJobs(data.results);
      setTotalResults(data.total);
      setTotalPages(data.pages);
      setPage(data.page);

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
      </Head>

      <main className="min-h-screen bg-slate-950 text-slate-100">
        <section className="mx-auto max-w-5xl px-6 py-20">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">
            JobLens
          </p>

          <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
            Find jobs more likely to be actively hiring.
          </h1>

          <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300">
            Active Hiring Confidence uses posting age, repeated observations, parallel openings,
            repost history, compensation, and applicant signals. It is an estimate, not a guarantee
            of employer intent. This tool is intended as a supplement to your research and judgment,
            not a replacement for it. Always verify the information and use your own discretion when
            applying for jobs.
          </p>

          <p className="mt-3 text-slate-400">
            Active Hiring Confidence (Ghost Job Filtering) · Repost tracking · Salary transparency
          </p>

          <form
            className="mt-8 grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-2 lg:grid-cols-4"
            onSubmit={(event) => {
              event.preventDefault();
              void load(1);
            }}
          >
            <input
              aria-label="Search jobs"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search title, company, city, or state"
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
            />

            <select
              aria-label="Role type"
              value={jobFamily}
              onChange={(event) => setJobFamily(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All role types</option>
              <option value="data analyst">Data analyst</option>
              <option value="data scientist">Data scientist</option>
              <option value="data engineer">Data engineer</option>
              <option value="software engineer">Software engineer</option>
              <option value="machine learning engineer">Machine learning engineer</option>
              <option value="business analyst">Business analyst</option>
              <option value="product manager">Product manager</option>
              <option value="technical program manager">Technical program manager</option>
              <option value="project manager">Project manager</option>
            </select>

            <div className="flex flex-col">
              <input
                aria-label="Max reported applicants"
                value={applicantMax}
                onChange={(event) => setApplicantMax(event.target.value)}
                placeholder="Max reported applicants"
                type="number"
                min="0"
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
              />

              {applicantMax && (
                <p role="note" className="mt-1.5 text-xs leading-5 text-amber-400">
                  Jobs with unavailable applicant count data are included in these results.
                </p>
              )}
            </div>

            <select
              aria-label="Job board"
              value={jobBoard}
              onChange={(event) => setJobBoard(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All job boards</option>
              <option value="company_site">Company site</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="glassdoor">Glassdoor</option>
              <option value="ziprecruiter">ZipRecruiter</option>
              <option value="dice">Dice</option>
              <option value="monster">Monster</option>
              <option value="jobright">Jobright</option>
              <option value="simplify">Simplify</option>
            </select>

            <select
              aria-label="Seniority"
              value={seniority}
              onChange={(event) => setSeniority(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All seniority</option>
              <option value="Entry">Entry</option>
              <option value="Mid">Mid</option>
              <option value="Senior">Senior</option>
              <option value="Lead">Lead</option>
              <option value="Executive">Executive</option>
            </select>

            <select
              aria-label="Employment type"
              value={employmentType}
              onChange={(event) => setEmploymentType(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All employment types</option>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Contract">Contract</option>
              <option value="Internship">Internship</option>
            </select>

            <select
              aria-label="Work arrangement"
              value={remoteType}
              onChange={(event) => setRemoteType(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All work types</option>
              <option value="Remote">Remote</option>
              <option value="Hybrid">Hybrid</option>
              <option value="Onsite">Onsite</option>
            </select>

            <select
              aria-label="Listing classification"
              value={classification}
              onChange={(event) => setClassification(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="">All listing types</option>
              <option value="original">Original</option>
              <option value="parallel">Parallel</option>
              <option value="repost">Repost</option>
            </select>

            <select
              aria-label="Sort jobs by"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="active_hiring_confidence">Sort by confidence</option>
              <option value="date_posted">Sort by posting date</option>
              <option value="date_first_seen">Sort by newest seen</option>
              <option value="ghost_job_probability">Sort by ghost probability</option>
              <option value="health_score">Sort by health score</option>
              <option value="salary_max">Sort by salary</option>
              <option value="applicant_count">Sort by applicants</option>
            </select>

            <select
              aria-label="Sort direction"
              value={sortDir}
              onChange={(event) => setSortDir(event.target.value as "asc" | "desc")}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="desc">High/new first</option>
              <option value="asc">Low/old first</option>
            </select>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={collapseCanonical}
                onChange={(event) => setCollapseCanonical(event.target.checked)}
                className="h-4 w-4"
              />
              Collapse related listings
            </label>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={includeOlderJobs}
                onChange={(event) => setIncludeOlderJobs(event.target.checked)}
                className="h-4 w-4"
              />
              Include jobs posted over {DEFAULT_MAX_AGE_DAYS} days ago
            </label>

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-cyan-300 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60 sm:col-span-2 lg:col-span-4"
            >
              {loading ? "Loading…" : "Search jobs"}
            </button>
          </form>

          {error && (
            <p className="mt-4 rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-red-200">
              {error}
            </p>
          )}

          {!loading && !error && totalResults !== null && (
            <div
              className="mt-8 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300"
              role="status"
              aria-live="polite"
            >
              {totalResults > 0 ? (
                <p>
                  Showing {firstVisibleResult}–{lastVisibleResult} of {totalResults} result
                  {totalResults === 1 ? "" : "s"}. Page {page} of {Math.max(totalPages, 1)}.
                  {!includeOlderJobs
                    ? ` Limited to jobs posted within the last ${DEFAULT_MAX_AGE_DAYS} days.`
                    : " Older jobs are included."}
                </p>
              ) : (
                <p>
                  No results found. Try clearing one or more filters, increasing the max reported
                  applicants value, or searching a broader city, state, title, or company.
                </p>
              )}
            </div>
          )}

          {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
            <nav
              aria-label="Top job results pagination"
              className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3"
            >
              <button
                type="button"
                onClick={() => load(page - 1, true)}
                disabled={page <= 1 || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <p className="text-sm text-slate-400">
                Page {page} of {totalPages}
              </p>

              <button
                type="button"
                onClick={() => load(page + 1, true)}
                disabled={page >= totalPages || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}

          {loading && jobs.length === 0 && (
            <div className="mt-10 grid gap-4" aria-label="Loading jobs">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={index}
                  className="h-36 animate-pulse rounded-xl border border-slate-800 bg-slate-900/70"
                />
              ))}
            </div>
          )}

          {!loading && !error && totalResults === 0 && (
            <div className="mt-10 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-center text-slate-300">
              No jobs match these filters. Try a broader search or clear one or more filters.
            </div>
          )}

          <div className="mt-10 grid gap-4">
            {jobs.map((job) => {
              const salary = formatSalary(job);
              const confidence = job.active_hiring_confidence;

              return (
                <article
                  key={job.id}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 p-5"
                >
                  <div className="flex flex-col justify-between gap-4 sm:flex-row">
                    <div>
                      <h2 className="text-xl font-semibold">{job.title_raw}</h2>

                      <p className="mt-1 text-slate-300">
                        {job.company.name} ·{" "}
                        {job.location_raw || job.remote_type || "Location unavailable"}
                      </p>

                      <p className="mt-1 text-sm text-slate-400">
                        {job.job_family || "Unknown role type"}
                        {job.seniority ? ` · ${job.seniority}` : ""}
                        {job.employment_type ? ` · ${job.employment_type}` : ""}
                        {job.remote_type ? ` · ${job.remote_type}` : ""}
                      </p>

                      <p className="mt-2 text-sm text-slate-400">
                        {job.listing_classification}
                        {job.repost_count > 0 ? ` · repost #${job.repost_count}` : ""}
                        {` · ${ageSummary(job)}`}
                        {job.applicant_count != null
                          ? ` · ${job.applicant_count} reported applicants`
                          : ""}
                        {salary ? ` · ${salary}` : ""}
                      </p>

                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-slate-400">Found on</span>

                        {sourceLinks(job).map(({ source, label }) => {
                          const safeUrl = safeExternalUrl(source.source_url);

                          return safeUrl ? (
                            <a
                              key={source.sighting_key}
                              href={safeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={`Open this listing on ${source.publisher_name}`}
                              className="rounded-full border border-cyan-500/40 bg-cyan-950/30 px-3 py-1 text-cyan-200 hover:border-cyan-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </a>
                          ) : (
                            <span
                              key={source.sighting_key}
                              title="The source URL was unavailable or invalid"
                              className="rounded-full border border-slate-700 px-3 py-1 text-slate-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </span>
                          );
                        })}
                      </div>
                    </div>

                    <div className="shrink-0 text-left sm:text-right">
                      <p
                        className={`confidence ${
                          confidence == null
                            ? "unknown"
                            : confidence >= 70
                              ? "high"
                              : confidence >= 45
                                ? "medium"
                                : "low"
                        }`}
                      >
                        {confidence == null ? "—" : Math.round(confidence)}
                      </p>

                      <p className="text-sm text-slate-400">{confidenceLabel(confidence)}</p>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          {!loading && !error && totalResults !== null && totalResults > 0 && totalPages > 1 && (
            <nav
              aria-label="Job results pagination"
              className="mt-8 flex items-center justify-between gap-4"
            >
              <button
                type="button"
                onClick={() => load(page - 1, true)}
                disabled={page <= 1 || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <p className="text-sm text-slate-400">
                Page {page} of {totalPages}
              </p>

              <button
                type="button"
                onClick={() => load(page + 1, true)}
                disabled={page >= totalPages || loading}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}
        </section>
      </main>
    </>
  );
}