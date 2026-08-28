// Canonical tags, robots.txt, and sitemap.xml all need the deployed origin.
// Falls back to localhost so dev/preview builds don't emit broken absolute
// URLs when NEXT_PUBLIC_SITE_URL hasn't been set for that environment.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
