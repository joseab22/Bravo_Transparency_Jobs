# Change Tracking

Mutable posting fields are recorded in `job_snapshots`. New snapshots are written when data changes or the configured minimum interval has elapsed. `job_events` records material title, description, salary, applicant, created, expired, and reactivated changes. Repost history is rebuilt from stored occurrences by the identity-analysis task.
