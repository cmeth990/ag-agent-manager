# Runbook: Stuck tasks (no heartbeat)

## When you see this

- Logs: `Stuck task detected: task_id (graph_run) last heartbeat: ...`
- API: `GET /queue/stuck?threshold_minutes=30` returns one or more tasks
- Worker or telemetry reports tasks in `IN_PROGRESS` for longer than the configured threshold (default 30 minutes)

## What it means

A task was dequeued and marked `IN_PROGRESS` but has not updated its **heartbeat** within the threshold. Common causes: worker crashed, long-running graph run (e.g. many sources), or a deadlock/hang.

## What to check

1. **List stuck tasks** – `GET /queue/stuck?threshold_minutes=30`. Note `task_id`, `task_type`, `domain`, `retry_count`, `last_heartbeat`, `started_at`.
2. **Worker health** – Is the worker process still running? Check process list, app logs, or your orchestrator (e.g. Railway, systemd). If the worker died, tasks stay IN_PROGRESS until marked stuck.
3. **Resource usage** – CPU/memory on the worker host; possible OOM or CPU saturation leading to slow progress and missed heartbeats.
4. **Payload size** – Very large payloads (e.g. huge `user_input` or state) can slow down the graph; consider limits.

## What to do

### Option A: Let auto-retry run (if enabled)

- If you run the stuck-task monitor with `auto_retry=True`, it will reset stuck tasks to `PENDING` (and increment retry count) so the worker can pick them up again. Check `GET /queue/stuck` response for `actions` (e.g. `auto_retry`).
- Ensure the worker is running and healthy before relying on auto-retry.

### Option B: Manually retry

- Use the same mechanism as DLQ triage if stuck tasks are moved to DLQ after max retries: `POST /queue/triage/{task_id}?action=retry`.
- If your code only marks stuck and doesn’t move to DLQ, you may need to update the task status to `PENDING` in the DB (or via an admin script) so the worker dequeues it again.

### Option C: Move to DLQ

- If a task is stuck repeatedly (e.g. retry_count already high), consider moving it to the dead-letter queue for triage (see RUNBOOK_DLQ.md) instead of retrying blindly.
- Some implementations do this automatically when `retry_count >= max_retries` for a stuck task.

### Restart worker

- If the worker crashed or is hung, restart it. After restart it will only pick up `PENDING` tasks; stuck tasks remain IN_PROGRESS until the stuck-task monitor resets them or you do so manually.

## Prevention

- **Heartbeats** – Ensure the worker (or graph) updates `heartbeat_at` regularly for long-running tasks (e.g. every 1–5 minutes). Our durable queue supports `heartbeat(task_id)`.
- **Timeout** – Consider a max duration for a single graph run; if exceeded, fail the task and let retry/DLQ handle it.
- **Stuck-task monitor** – Run a periodic job (e.g. every 5 minutes) that calls the stuck-task logic and optionally auto-retries. See `app/queue/heartbeat.py` (`monitor_stuck_tasks`, `start_heartbeat_monitor`).

## Configuration

- Stuck threshold: default 30 minutes (configurable in the API and in the monitor).
- Poll interval for the worker: see `app/queue/worker.py` and `POLL_INTERVAL_SECONDS`.

## Links

- API: `GET /queue/stuck`
- Implementation: `app/queue/durable_queue.py` (`get_stuck_tasks`), `app/queue/heartbeat.py`
