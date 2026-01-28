# Runbook: Tasks in the dead-letter queue (DLQ)

## When you see this

- Logs: `Task X moved to dead-letter queue after N retries`
- API: `GET /queue/dead-letter` returns one or more tasks
- Alerts or dashboards showing DLQ count > 0

## What it means

Tasks that failed repeatedly (after max retries) have been moved to the **dead-letter queue** instead of being retried again. They are stored in Postgres with status `dead_letter` and need triage.

## What to check

1. **List DLQ tasks** – `GET /queue/dead-letter?limit=50`. Note `task_id`, `task_type`, `domain`, `source`, `error`, `retry_count`, `created_at`.
2. **Error patterns** – Group by `error` or `task_type`. Common causes: timeout, 429 rate limit, budget exceeded, validation error, upstream API down.
3. **Volume** – If many tasks share the same error, fix the root cause first (e.g. circuit breaker, rate limit, or bug).

## What to do

### Retry a single task (same payload)

- `POST /queue/triage/{task_id}?action=retry`
- Use when the failure was transient (e.g. timeout, brief outage) and you haven’t changed anything.

### Retry with an updated payload

- `POST /queue/triage/{task_id}?action=update_payload` with body including `updated_payload` (e.g. corrected domain or parameters).
- Use when the payload was wrong (e.g. bad domain name) or you want to reduce scope (e.g. fewer sources).

### Skip / leave in DLQ

- `POST /queue/triage/{task_id}?action=skip` (or leave as-is). Use when the task is obsolete or not worth retrying.

### Bulk handling

- Fix the underlying issue (e.g. circuit breaker, rate limit, budget, or code bug), then retry tasks one by one or in small batches via the triage API.
- If the same task type keeps failing, add logging or metrics before triaging more.

## Prevention

- Ensure retries use exponential backoff so transient failures don’t burn retries too fast.
- Use circuit breakers and rate limiting so one bad source doesn’t flood the DLQ.
- Set budgets and caps so “budget exceeded” tasks don’t retry endlessly.

## Links

- API: `GET /queue/dead-letter`, `POST /queue/triage/{task_id}`
- Implementation: `app/queue/durable_queue.py` (fail → DEAD_LETTER), `app/queue/triage.py`
