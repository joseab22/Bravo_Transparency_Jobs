# Change Tracking & Job Update Detection

JobLens tracks changes to job postings over time at three levels:
snapshot history, repost detection, and company-level analytics.

---

## How job changes are tracked

### 1. JobSnapshot (point-in-time records)

Every time the scraper sees a job it already knows about, it writes a `job_snapshots` row:

```sql
-- See how applicant count grew over time for a job
SELECT snapshot_at, applicant_count
FROM job_snapshots
WHERE job_posting_id = 123
ORDER BY snapshot_at;
```

Fields tracked per snapshot: `applicant_count`, `salary_min`, `salary_max`, `is_active`, `title_raw`

This lets you chart: "this job went from 50 → 1,200 applicants in 3 weeks" — a strong ghost job signal.

### 2. RepostEvent (repost history)

When a job_identity_key disappears (is_active flips False) and then reappears, a `repost_events` row is written:

```sql
-- Full repost history for a role
SELECT occurrence_number, date_seen, source, days_since_previous
FROM repost_events
WHERE job_identity_key = 'techcorp__data_analyst__los_angeles'
ORDER BY occurrence_number;
```

### 3. JobSourceSighting (cross-platform tracking)

Every platform a job appears on is logged:

```sql
-- See all platforms a job is on and when each was last active
SELECT source, first_seen, last_seen, applicant_count
FROM job_source_sightings
WHERE job_posting_id = 123;
```

---

## Scores that update automatically

The Celery beat scheduler re-scores all active jobs every 3 hours.
Scores that change over time:

| Score | Why it changes |
|---|---|
| `ghost_job_probability` | Repost count grows, days_active increments |
| `health_score` | Derived from ghost_prob + applicant velocity |
| `competition_score` | Applicant count changes on every scrape |
| `interview_opportunity_score` | Degrades as days_active increases |

---

## Querying job changes

### Jobs whose ghost risk grew significantly this week

```sql
SELECT
  jp.title_normalized,
  c.name AS company,
  jp.ghost_job_probability AS current_ghost,
  jp.repost_count,
  jp.days_active
FROM job_postings jp
JOIN companies c ON c.id = jp.company_id
WHERE jp.is_active = TRUE
  AND jp.ghost_job_probability > 0.6
  AND jp.days_active BETWEEN 7 AND 90
ORDER BY jp.ghost_job_probability DESC
LIMIT 50;
```

### Jobs with rapidly growing applicant counts (competition spike)

```sql
SELECT
  jp.id,
  jp.title_normalized,
  c.name,
  MIN(js.applicant_count) AS initial_applicants,
  MAX(js.applicant_count) AS current_applicants,
  MAX(js.applicant_count) - MIN(js.applicant_count) AS growth
FROM job_postings jp
JOIN companies c ON c.id = jp.company_id
JOIN job_snapshots js ON js.job_posting_id = jp.id
GROUP BY jp.id, jp.title_normalized, c.name
HAVING MAX(js.applicant_count) - MIN(js.applicant_count) > 500
ORDER BY growth DESC;
```

### Companies with highest repost rates (serial ghost-posters)

```sql
SELECT
  c.name,
  COUNT(DISTINCT re.job_identity_key) AS roles_reposted,
  AVG(jp.repost_count) AS avg_reposts_per_role,
  AVG(jp.ghost_job_probability) AS avg_ghost_prob
FROM companies c
JOIN job_postings jp ON jp.company_id = c.id
JOIN repost_events re ON re.job_posting_id = jp.id
GROUP BY c.name
HAVING COUNT(DISTINCT re.job_identity_key) >= 3
ORDER BY avg_ghost_prob DESC;
```

### New postings in last 24 hours

```sql
SELECT jp.title_normalized, c.name, jp.source, jp.date_first_seen
FROM job_postings jp
JOIN companies c ON c.id = jp.company_id
WHERE jp.date_first_seen >= NOW() - INTERVAL '24 hours'
ORDER BY jp.date_first_seen DESC;
```

---

## Expiration logic

Jobs are marked `is_active = FALSE` when not seen in 14 days (configurable).
This runs nightly via `task_expire_stale_jobs`.

Inactive jobs are kept in the DB — they feed the company-level `ghost_job_rate`
and `avg_reposts` metrics, and are counted in repost detection if the role re-appears.

---

## Adding email/webhook alerts (next steps)

To get notified when a job you're watching changes:

1. Add a `watched_jobs` table: `{user_id, job_posting_id, created_at}`
2. Add a Celery task that runs after scoring: check if watched jobs' `ghost_job_probability` crossed 0.60 since last check
3. Send email via SendGrid or webhook to Slack/Discord
4. Alternatively: expose a `/api/v1/jobs/{id}/watch` endpoint and return a feed URL

---

## Monitoring scraper health

Check the Celery task result backend (Redis) for task outcomes:

```bash
# From the worker container
celery -A app.workers.celery_app inspect active
celery -A app.workers.celery_app inspect scheduled
celery -A app.workers.celery_app events   # live event stream
```

Or query the Celery result backend from Python:

```python
from app.workers.celery_app import celery_app
result = celery_app.AsyncResult("task-id-here")
print(result.state, result.result)
```
