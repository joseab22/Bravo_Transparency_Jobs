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
  const sources = job.canonical_sources.length ? job.canonical_sources : [{
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
  }];
  const totals = sources.reduce<Record<string, number>>((counts, source) => {
    counts[source.publisher_name] = (counts[source.publisher_name] || 0) + 1;
    return counts;
  }, {});
  const seen: Record<string, number> = {};
  return sources.map((source) => {
    seen[source.publisher_name] = (seen[source.publisher_name] || 0) + 1;
    const label = totals[source.publisher_name] > 1
      ? `${source.publisher_name} ${seen[source.publisher_name]}`
      : source.publisher_name;
    return { source, label };
  });
}

function formatSalary(job: JobListItem): string | null {
  if (!job.salary_listed || (job.salary_min == null && job.salary_max == null)) return null;
  const formatter = new Intl.NumberFormat("en-US", { style: "currency", currency: job.salary_currency || "USD", maximumFractionDigits: 0 });
  if (job.salary_min != null && job.salary_max != null) return `${formatter.format(job.salary_min)}–${formatter.format(job.salary_max)}`;
  return formatter.format(job.salary_min ?? job.salary_max ?? 0);
}

export default function Home() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await jobsApi.list({
        page: 1,
        page_size: 20,
        collapse_canonical: true,
        sort_by: "active_hiring_confidence",
        sort_dir: "desc",
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
        <meta name="description" content="Posting history and active-hiring signals for technology roles." />
      </Head>
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <section className="mx-auto max-w-5xl px-6 py-20">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">JobLens</p>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">Find jobs more likely to be actively hiring.</h1>
          <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300">
            Active Hiring Confidence uses posting age, repeated observations, parallel openings, repost history, compensation, and applicant signals. It is an estimate—not a guarantee of employer intent.
          </p>
          <p className="mt-3 text-slate-400">Active Hiring Confidence (Ghost Job Filtering) · Repost tracking · Salary transparency</p>
          <button onClick={load} disabled={loading} className="mt-8 rounded-lg bg-cyan-300 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60">
            {loading ? "Loading…" : "Load jobs from API"}
          </button>
          {error && <p className="mt-4 rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-red-200">{error}</p>}

          <div className="mt-10 grid gap-4">
            {jobs.map((job) => {
              const salary = formatSalary(job);
              const confidence = job.active_hiring_confidence;
              return (
                <article key={job.id} className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                  <div className="flex flex-col justify-between gap-4 sm:flex-row">
                    <div>
                      <h2 className="text-xl font-semibold">{job.title_raw}</h2>
                      <p className="mt-1 text-slate-300">{job.company.name} · {job.location_raw || job.remote_type || "Location unavailable"}</p>
                      <p className="mt-2 text-sm text-slate-400">{job.listing_classification} · {job.days_active} days observed{salary ? ` · ${salary}` : ""}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-slate-400">Found on</span>
                        {sourceLinks(job).map(({ source, label }) => (
                          source.source_url ? (
                            <a
                              key={source.sighting_key}
                              href={source.source_url}
                              target="_blank"
                              rel="noreferrer"
                              title={`Open this listing on ${source.publisher_name}`}
                              className="rounded-full border border-cyan-500/40 bg-cyan-950/30 px-3 py-1 text-cyan-200 hover:border-cyan-300"
                            >
                              {label}{source.is_direct ? " · Direct" : ""}
                            </a>
                          ) : (
                            <span key={source.sighting_key} className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
                              {label}{source.is_direct ? " · Direct" : ""}
                            </span>
                          )
                        ))}
                      </div>
                    </div>
                    <div className="shrink-0 text-left sm:text-right">
                      <p className={`confidence ${confidence == null ? "unknown" : confidence >= 70 ? "high" : confidence >= 45 ? "medium" : "low"}`}>
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
