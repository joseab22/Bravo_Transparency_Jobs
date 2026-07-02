import { useState } from "react";
import Head from "next/head";
import type { JobListItem } from "@/types/jobs";
import { jobsApi } from "@/lib/api";

// Placeholder home page — wire up to your component library as you build out the UI.
export default function Home() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await jobsApi.list({ page: 1, page_size: 20, sort_by: "health_score" });
      setJobs(data.results);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Head>
        <title>JobLens — Job Market Transparency</title>
        <meta name="description" content="Measure active hiring confidence, track reposts, and compare salary transparency." />
      </Head>
      <main className="max-w-4xl mx-auto px-4 py-10">
        <h1 className="text-3xl font-semibold mb-2">JobLens</h1>
        <p className="text-gray-500 mb-8">Active Hiring Confidence (Ghost Job Filtering) · Repost tracking · Salary transparency</p>
        <button
          onClick={load}
          className="px-5 py-2 bg-black text-white rounded-lg text-sm mb-8"
        >
          {loading ? "Loading…" : "Load jobs from API"}
        </button>
        <ul className="space-y-4">
          {jobs.map((job) => (
            <li key={job.id} className="border rounded-xl p-4 bg-white shadow-sm">
              <div className="flex justify-between">
                <div>
                  <p className="font-medium">{job.title_raw}</p>
                  <p className="text-sm text-gray-500">{job.company.name} · {job.location_raw}</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full border font-medium ${
                    (job.active_hiring_confidence ?? 0) >= 70 ? "score-low" :
                    (job.active_hiring_confidence ?? 0) >= 40 ? "score-med" : "score-high"
                  }`}>
                    Active Hiring: {(job.active_hiring_confidence ?? 0).toFixed(0)}%
                  </span>
                  <span className="text-xs text-gray-500 capitalize">
                    {job.listing_classification}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
