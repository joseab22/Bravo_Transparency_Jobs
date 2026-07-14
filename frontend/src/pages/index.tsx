import Head from "next/head";
import { useState } from "react";

import { jobsApi } from "@/lib/api";
import type { JobListItem } from "@/types/jobs";

function confidenceLabel(value?: number | null): string {
  if (value == null) return "Not scored";
  if (value >= 70) return "Higher confidence";
  if (value >= 45) return "Mixed signals";
  return "Lower confidence";
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
          last_seen: job.date_first_seen,
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [jobFamily, setJobFamily] = useState("");
  const [jobBoard, setJobBoard] = useState("");
  const [seniority, setSeniority] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [remoteType, setRemoteType] = useState("");
  const [classification, setClassification] = useState("");
  const [sortBy, setSortBy] = useState("active_hiring_confidence");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [collapseCanonical, setCollapseCanonical] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const data = await jobsApi.list({
        page: 1,
        page_size: 50,
        q: q || undefined,
        job_family: jobFamily || undefined,
        job_board: jobBoard || undefined,
        seniority: seniority || undefined,
        employment_type: employmentType || undefined,
        remote_type: remoteType || undefined,
        classification: classification || undefined,
        collapse_canonical: collapseCanonical,
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      setJobs(data.results);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load jobs");
    } finally {
      setLoading(false);
    }
  }

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

          <div className="mt-8 grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search title/company"
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder:text-slate-500"
            />

            <select
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

            
            <label className="grid gap-1 text-sm text-slate-300">
              <select
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
text = text.replace('  ', "")
              </select>
            </label>

<select
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
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            >
              <option value="active_hiring_confidence">Sort by confidence</option>
              <option value="date_first_seen">Sort by newest seen</option>
              <option value="days_active">Sort by days active</option>
              <option value="ghost_job_probability">Sort by ghost probability</option>
              <option value="health_score">Sort by health score</option>
              <option value="salary_max">Sort by salary</option>
              <option value="applicant_count">Sort by applicants</option>
            </select>

            <select
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
          </div>

          <button
            onClick={load}
            disabled={loading}
            className="mt-6 rounded-lg bg-cyan-300 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60"
          >
            {loading ? "Loading…" : "Load jobs from API"}
          </button>

          {error && (
            <p className="mt-4 rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-red-200">
              {error}
            </p>
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
                        · {job.days_active} days observed
                        {salary ? ` · ${salary}` : ""}
                      </p>

                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-slate-400">Found on</span>

                        {sourceLinks(job).map(({ source, label }) =>
                          source.source_url ? (
                            <a
                              key={source.sighting_key}
                              href={source.source_url}
                              target="_blank"
                              rel="noreferrer"
                              title={`Open this listing on ${source.publisher_name}`}
                              className="rounded-full border border-cyan-500/40 bg-cyan-950/30 px-3 py-1 text-cyan-200 hover:border-cyan-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </a>
                          ) : (
                            <span
                              key={source.sighting_key}
                              className="rounded-full border border-slate-700 px-3 py-1 text-slate-300"
                            >
                              {label}
                              {source.is_direct ? " · Direct" : ""}
                            </span>
                          ),
                        )}
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
        </section>
      </main>
    </>
  );
}
