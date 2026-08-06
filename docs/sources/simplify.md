# Simplify

Simplify is a keyless source. JobLens reads configurable public JSON feeds for:

- SimplifyJobs New Grad Positions;
- SimplifyJobs Summer 2026 Internships.

The parser deduplicates stable IDs/URLs, stores all listed locations in one normalized label, and performs no geocoding. It also acts on the feed's own `is_closed`/`active` flags: a record the feed reports as closed is never used to create a new row, but if it matches an existing active row, that row is deactivated and a `JobEvent` records why -- the closed signal is evidence, not just a filter.

Simplify is intentionally excluded from JSearch queries and response attribution because the direct feeds are more efficient and do not consume JSearch/OpenWeb Ninja quota. Direct Simplify collection remains enabled independently with:

```env
ENABLED_SCRAPER_SOURCES=simplify,jsearch
```
