# Simplify

Simplify is a keyless source. JobLens reads configurable public JSON feeds for:

- SimplifyJobs New Grad Positions;
- SimplifyJobs Summer 2026 Internships.

The parser keeps open records, deduplicates stable IDs/URLs, stores all listed locations in one normalized label, and performs no geocoding.

Simplify is intentionally excluded from JSearch queries and response attribution because the direct feeds are more efficient and do not consume JSearch/OpenWeb Ninja quota. Direct Simplify collection remains enabled independently with:

```env
ENABLED_SCRAPER_SOURCES=simplify,jsearch
```
