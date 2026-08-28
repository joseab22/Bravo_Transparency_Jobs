import type { GetServerSideProps } from "next";

import { SITE_URL } from "@/lib/seo";

// Only the two static routes are listed. Individual job listings have no
// distinct crawlable URL yet -- they render inside a detail panel on "/"
// rather than a route of their own -- so they can't be listed here until
// that changes.
const STATIC_ROUTES = ["/", "/profile", "/terms", "/privacy"];

export const getServerSideProps: GetServerSideProps = async ({ res }) => {
  const urls = STATIC_ROUTES.map((path) => `  <url><loc>${SITE_URL}${path}</loc></url>`).join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;

  res.setHeader("Content-Type", "application/xml");
  res.write(body);
  res.end();
  return { props: {} };
};

export default function SitemapXml() {
  return null;
}
