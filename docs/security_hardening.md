# Security hardening included in this package

## Applied now

- CORS is restricted to origins listed in `CORS_ORIGINS`.
- Public browser access is limited to `GET` and `OPTIONS` requests.
- Job search parameters have explicit type, length, range, and enum validation.
- Sort fields use a fixed SQLAlchemy column map instead of dynamic attribute lookup.
- Scraped external links accept only valid HTTP/HTTPS URLs without embedded credentials.
- Next.js emits anti-sniffing, anti-framing, referrer, permissions, and opener headers.
- The job score mutation endpoint requires `X-Admin-Key`.
- The deployment Nginx config includes public and administrative request limits.
- Docker Compose keeps PostgreSQL and Redis internal and binds the app to localhost.
- Backend and frontend images already run as unprivileged users, with
  `no-new-privileges` enabled in Compose.

## Required local secret

Add a generated value to `backend/.env`:

```env
CORS_ORIGINS=http://localhost:3000
ADMIN_API_KEY=<64-character generated hex value>
JSEARCH_PAGES_PER_QUERY=3
JSEARCH_SCHEDULE_EVERY_HOURS=6
JSEARCH_REQUEST_RESERVE=1400
```

Generate it with:

```bash
openssl rand -hex 32
```

Never prefix the admin key with `NEXT_PUBLIC_` and never commit `backend/.env`.

## Deployment-only step

Replace `yourdomain.com` in `infrastructure/nginx/nginx.conf`, install the TLS
certificate, and route public traffic through Nginx. HSTS is intentionally not
included until the production domain is confirmed to be HTTPS-only.
