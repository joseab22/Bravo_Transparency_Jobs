# Identity Resolution

JobLens treats a posting as structured data rather than one normalized title string.

## Title structure

`decompose_title()` extracts:

- canonical technology job family;
- seniority;
- zero or more specialization tags;
- parse confidence.

Example:

```text
Senior Software Engineer - Admin
→ family: software engineer
→ seniority: Senior
→ specialization: admin
```

```text
Senior Software Engineer - Lead
→ family: software engineer
→ seniority: Senior
→ specialization: tech_lead
```

Those roles are not merged.

## Listing identity

The location-independent fingerprint includes company, job family, specialization, seniority, employment type, and work arrangement. The human-readable key also includes a location bucket.

Ingestion upserts only on stable source identifiers or URLs when available. It does not collapse distinct source IDs merely because their titles and locations are similar, which preserves simultaneous headcount listings.

## Classification

- **Original:** no compatible earlier occurrence.
- **Parallel:** compatible listings overlap in time or are posted within the configured parallel window. Remote or regional advertisements can be parallel.
- **Repost:** a compatible earlier listing was inactive before the new occurrence, the minimum gap elapsed, and location/work arrangement is compatible.

Remote and onsite listings are not equivalent. Distinct non-empty specializations are not merged. Structured fields are primary; lexical title matching is bounded to the most recent candidate set. Semantic title matching and description embeddings are opt-in so a large history rebuild does not unexpectedly download or run a model.

Relevant settings:

```env
PARALLEL_LISTING_WINDOW_DAYS=2
REPOST_MIN_GAP_DAYS=7
CANDIDATE_HISTORY_DAYS=365
IDENTITY_CANDIDATE_LIMIT=100
SEMANTIC_TITLE_MATCHING_ENABLED=false
DESCRIPTION_EMBEDDINGS_ENABLED=false
```

## Analysis lifecycle

Collection inserts and updates records first. The authoritative historical pass is:

```text
joblens.run_repost_detection
```

It rebuilds classification for the configured history window and only replaces repost events associated with the processed jobs. Any classification change clears old scores so Active Hiring Confidence is recalculated from current history.

Two boundary behaviors follow from this and are worth stating explicitly:

- A posting older than `CANDIDATE_HISTORY_DAYS` is not re-evaluated by a rebuild and cannot be selected as a candidate for a newer posting. If a genuine repost gap exceeds that window, the newer occurrence becomes a fresh `original` root rather than being linked to the older history; the canonical group effectively restarts at the window boundary instead of spanning it.
- `RepostEvent` rows are replaced, not appended, for every job processed by a rebuild. They describe the current classification's supporting detail, not an immutable audit log; `JobEvent` rows (created, title/description/salary changes, reactivation) remain the append-only historical record and are never deleted by a rebuild.

## Source-aware canonical display

Source duplication and role-history classification are related but distinct:

- repeated `collection_provider + external_id` records update one posting;
- multiple publishers for that provider record are retained as source sightings;
- different stable external IDs are not discarded during ingestion;
- compatible rows can later share a `canonical_job_id` and be classified as parallel or repost occurrences;
- collapsed API responses aggregate all publisher sightings across that canonical group.

Thus, source evidence remains available even when the frontend shows one representative card.
