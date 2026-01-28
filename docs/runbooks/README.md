# Operational Runbooks

Short, actionable runbooks for common failure modes. Use with telemetry and admin APIs.

| Runbook | When to use |
|---------|-------------|
| [RUNBOOK_CIRCUIT_BREAKER.md](RUNBOOK_CIRCUIT_BREAKER.md) | A domain or source is paused (circuit open). |
| [RUNBOOK_DLQ.md](RUNBOOK_DLQ.md) | Tasks are in the dead-letter queue and need triage. |
| [RUNBOOK_BUDGET_EXCEEDED.md](RUNBOOK_BUDGET_EXCEEDED.md) | Cost cap hit; requests rejected with budget error. |
| [RUNBOOK_STUCK_TASKS.md](RUNBOOK_STUCK_TASKS.md) | Tasks stuck IN_PROGRESS (no heartbeat). |

**Telemetry:** `GET /telemetry/state`, `GET /telemetry/summary`  
**Queue:** `GET /queue/dead-letter`, `GET /queue/stuck`, `POST /queue/triage/{task_id}`

**Auth:** If `ADMIN_API_KEY` is set, send it on every request: header `X-Admin-Key: <key>` or `Authorization: Bearer <key>`.
