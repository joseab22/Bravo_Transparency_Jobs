# Simplify

Default keyless source. JobLens reads the configurable public JSON feeds for:

- SimplifyJobs New Grad Positions;
- SimplifyJobs Summer 2026 Internships.

The parser keeps open records, deduplicates stable IDs/URLs, stores all listed locations in one normalized label, and performs no geocoding. Feed URLs and the maximum retained record count are configurable in `.env`.
