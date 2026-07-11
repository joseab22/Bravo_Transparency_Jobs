# Indeed through JSearch

This optional targeted adapter adds `via indeed` to JSearch queries and uses the same `RAPIDAPI_KEY`, cursor pagination, request counter, and publisher parser as generic JSearch.

Returned rows are not blindly labeled Indeed. JobLens uses the response publisher/apply metadata and retains every application option.

Do not include both `jsearch` and `indeed` in `ENABLED_SCRAPER_SOURCES` under normal operation. The generic source already returns Indeed results and prevents unnecessary duplicate requests. The settings validator rejects this overlap unless `ALLOW_OVERLAPPING_JSEARCH_SOURCES=true`.
