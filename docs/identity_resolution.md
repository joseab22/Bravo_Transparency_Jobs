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
