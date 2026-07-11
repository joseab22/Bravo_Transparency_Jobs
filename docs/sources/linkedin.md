# LinkedIn through JSearch

This optional targeted adapter adds `via linkedin` to JSearch queries and uses the same `RAPIDAPI_KEY`, cursor pagination, request counter, and publisher parser as generic JSearch. It does not use LinkedIn OAuth credentials.

Returned rows are not blindly labeled LinkedIn. JobLens uses response publisher/apply metadata and retains every application option.

Do not include both `jsearch` and `linkedin` in `ENABLED_SCRAPER_SOURCES` under normal operation. The generic source already returns LinkedIn results and prevents unnecessary duplicate requests. The settings validator rejects this overlap unless `ALLOW_OVERLAPPING_JSEARCH_SOURCES=true`.
