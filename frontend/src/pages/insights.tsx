import { useEffect, useState } from "react";
import Head from "next/head";

import { BarList } from "@/components/BarList";
import { CARD } from "@/lib/designSystem";
import { jobsApi } from "@/lib/api";
import { SITE_URL } from "@/lib/seo";
import { PAGE_TITLE, SECTION_TITLE } from "@/lib/typography";
import type { MarketStats } from "@/types/jobs";

const CLASSIFICATION_LABEL: Record<string, string> = {
  original: "Original postings",
  parallel: "Parallel openings",
  repost: "Reposts",
};

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className={`${CARD} p-5`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-4xl font-bold tracking-tight text-slate-100">{value}</p>
      {hint && <p className="mt-1 text-sm text-slate-400">{hint}</p>}
    </div>
  );
}

export default function Insights() {
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    jobsApi
      .stats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load market insights.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <Head>
        <title>Market Insights | JobLens</title>
        <meta
          name="description"
          content="Aggregate active-hiring signals across every job JobLens tracks: posting reliability, ghost-job risk, top industries and skills."
        />
        <link rel="canonical" href={`${SITE_URL}/insights`} />
      </Head>

      <section className="mx-auto max-w-[90rem] px-6 py-12">
        <div className="max-w-3xl">
          <h1 className={PAGE_TITLE}>Market insights</h1>
          <p className="mt-2 text-slate-300">
            Aggregate signals across every currently active listing JobLens tracks. These are
            market-wide averages, not a prediction for any single job.
          </p>
        </div>

        {loading && (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Loading market insights">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className={`h-28 animate-pulse ${CARD}`} />
            ))}
          </div>
        )}

        {!loading && error && (
          <p role="alert" className="mt-8 rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-200">
            {error}
          </p>
        )}

        {!loading && !error && stats && (
          <>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <StatTile label="Active listings tracked" value={stats.total_active_jobs.toLocaleString()} />
              <StatTile
                label="Avg active-hiring confidence"
                value={`${stats.avg_active_hiring_confidence.toFixed(0)}/100`}
                hint={`${stats.scored_active_jobs.toLocaleString()} scored`}
              />
              <StatTile
                label="Avg estimated ghost-job risk"
                value={`${(stats.avg_ghost_probability * 100).toFixed(0)}%`}
              />
              <StatTile
                label="High-risk listings"
                value={stats.high_ghost_risk_count.toLocaleString()}
                hint="Estimated risk of 60% or higher"
              />
              <StatTile label="Avg days a listing stays active" value={stats.avg_days_active.toFixed(0)} />
              <StatTile label="Total reported applicants" value={stats.total_applicants.toLocaleString()} />
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              <div className={`${CARD} p-5`}>
                <h2 className={SECTION_TITLE}>Listing pattern</h2>
                <div className="mt-4">
                  <BarList
                    items={stats.classification_counts.map((row) => ({
                      label: CLASSIFICATION_LABEL[row.classification] ?? row.classification,
                      count: row.count,
                    }))}
                  />
                </div>
              </div>

              <div className={`${CARD} p-5`}>
                <h2 className={SECTION_TITLE}>Top industries</h2>
                <div className="mt-4">
                  <BarList items={stats.top_industries.map((row) => ({ label: row.industry, count: row.count }))} />
                </div>
              </div>

              <div className={`${CARD} p-5`}>
                <h2 className={SECTION_TITLE}>Top skills</h2>
                <div className="mt-4">
                  <BarList items={stats.top_skills.map((row) => ({ label: row.skill, count: row.count }))} />
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
