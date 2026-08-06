# Indeed through JSearch

This optional targeted adapter adds `via indeed` to JSearch queries and uses the same `OPENWEBNINJA_API_KEY`, cursor pagination, request counter, and publisher parser as generic JSearch.

Returned rows are not blindly labeled Indeed. JobLens uses the response publisher/apply metadata and retains every application option. A result with no Indeed-attributed apply option at all is dropped rather than stored under a publisher it doesn't actually have evidence for.

Do not include both `jsearch` and `indeed` in `ENABLED_SCRAPER_SOURCES` under normal operation. The generic source already returns Indeed results and prevents unnecessary duplicate requests. The settings validator rejects this overlap unless `ALLOW_OVERLAPPING_JSEARCH_SOURCES=true`.
