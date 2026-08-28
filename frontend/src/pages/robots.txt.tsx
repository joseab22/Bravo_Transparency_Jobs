import type { GetServerSideProps } from "next";

import { SITE_URL } from "@/lib/seo";

// Served as a real page rather than a static /public file so the Sitemap
// line always points at the deployed origin (NEXT_PUBLIC_SITE_URL) instead
// of a value baked in at a different environment's build time.
export const getServerSideProps: GetServerSideProps = async ({ res }) => {
  res.setHeader("Content-Type", "text/plain");
  res.write(["User-agent: *", "Allow: /", "", `Sitemap: ${SITE_URL}/sitemap.xml`, ""].join("\n"));
  res.end();
  return { props: {} };
};

export default function RobotsTxt() {
  return null;
}
