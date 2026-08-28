import type { GetServerSideProps } from "next";

import { SITE_URL } from "@/lib/seo";
import type { PaginatedJobs } from "@/types/jobs";

const STATIC_ROUTES = ["/", "/profile", "/insights", "/terms", "/privacy"];

// Individual job pages now exist at /jobs/[id]. Capped to the top few
// hundred by active-hiring confidence rather than every active listing --
// this route fetches synchronously on every crawl, and the max page_size
// the list endpoint allows is 100, so pulling thousands would mean
// thousands of extra backend round trips on a single request. Well under
// a search engine's own per-sitemap limits either way.
const JOB_PAGES_TO_FETCH = 3;
const PAGE_SIZE = 100;

async function fetchJobIds(backend: string): Promise<number[]> {
  const ids: number[] = [];
  for (let page = 1; page <= JOB_PAGES_TO_FETCH; page += 1) {
    const response = await fetch(
      `${backend}/api/v1/jobs?page=${page}&page_size=${PAGE_SIZE}&sort_by=active_hiring_confidence&sort_dir=desc`,
    );
    if (!response.ok) break;
    const data = (await response.json()) as PaginatedJobs;
    ids.push(...data.results.map((job) => job.id));
    if (data.results.length < PAGE_SIZE) break;
  }
  return ids;
}

export const getServerSideProps: GetServerSideProps = async ({ res }) => {
  const backend = (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(/\/$/, "");

  let jobIds: number[] = [];
  try {
    jobIds = await fetchJobIds(backend);
  } catch {
    // A sitemap missing job URLs for one request is far better than a 500 --
    // the static routes below still get served.
  }

  const urls = [
    ...STATIC_ROUTES.map((path) => `  <url><loc>${SITE_URL}${path}</loc></url>`),
    ...jobIds.map((id) => `  <url><loc>${SITE_URL}/jobs/${id}</loc></url>`),
  ].join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;

  res.setHeader("Content-Type", "application/xml");
  res.write(body);
  res.end();
  return { props: {} };
};

export default function SitemapXml() {
  return null;
}
