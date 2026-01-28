# Runbook: Budget exceeded (cost cap hit)

## When you see this

- Logs: `Budget exceeded: ...` or `BudgetExceededError`
- Logs: `Budget envelope exceeded` (per-task, per-agent, per-queue, or per-tool)
- API/telemetry: cost tracking shows spend at or over a configured limit
- Users/agents see requests rejected with a budget-related error

## What it means

A cost cap has been enforced: global daily, per-domain daily, per-agent daily, per-queue concurrency, or per-tool call. Further LLM (or other billable) calls are blocked until the next window or until limits are raised.

## What to check

1. **Telemetry** – `GET /telemetry/state` (or `/telemetry/summary`). Check `cost` / `budget` section: daily spend, per-domain spend, remaining budget.
2. **Which cap** – Error message usually says which envelope or scope (e.g. “Global daily budget exceeded”, “Agent 'extractor' daily cap exceeded”).
3. **Recent usage** – Cost tracker or logs: which agent/domain/queue is driving spend.

## What to do

### Short-term: allow critical work

- **Raise the cap** – If you use env vars (e.g. `LLM_DAILY_BUDGET_USD`, `COST_PER_AGENT_DAILY_CAP_USD`), increase the value and restart (or reload config if supported). Use sparingly and only after confirming the need.
- **Defer non-urgent work** – Rely on “defer to next window” behavior: e.g. daily caps reset at midnight UTC; new requests then get budget again.

### Medium-term: reduce burn

- **Model tiering** – Ensure cheap tasks (triage, classification, source filtering) use the cheap tier; reserve expensive models for complex tasks only.
- **Caching** – Verify extraction/source results are cached so repeated inputs don’t call the LLM again.
- **Cheap verification** – Use regex/NER first; call LLMs only when needed.
- **Rate limiting** – Avoid bursts that trigger many LLM calls in a short time.

### Optional: require approval for high spend

- If you have a “require human review for more spend” path, use it for large or risky operations so caps can stay low while still allowing approved overrides.

## Configuration reference

- Global daily: `LLM_DAILY_BUDGET_USD`
- Per-domain: `DOMAIN_BUDGET_<DOMAIN>` (e.g. `DOMAIN_BUDGET_Algebra=1.00`)
- Per-task: `COST_PER_TASK_CAP_USD`
- Per-agent daily: `COST_PER_AGENT_DAILY_CAP_USD`
- Per-tool call: `COST_PER_TOOL_CALL_CAP_USD`

See `app/cost/budget.py`, `app/cost/envelopes.py`, and `docs/COST_CONTROL.md`.

## Prevention

- Set realistic caps and monitor dashboards so you see trends before hitting limits.
- Use budget envelopes (per-task, per-agent, per-tool) so one flow can’t consume the whole budget.
- Alert when spend reaches e.g. 80% of a cap so you can adjust or investigate.

## Links

- Implementation: `app/cost/budget.py`, `app/cost/envelopes.py`, `app/llm/tracked_client.py` (enforcement)
