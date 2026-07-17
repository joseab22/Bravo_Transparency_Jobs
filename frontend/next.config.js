/** @type {import('next').NextConfig} */

const securityHeaders = [
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Cross-Origin-Opener-Policy",
    value: "same-origin",
  },
];

const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";

    return [
      {
        source: "/api/v1/jobs",
        destination: `${backend}/api/v1/jobs/`,
      },
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

module.exports = nextConfig;
