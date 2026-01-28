# Runbook: Circuit breaker open for a domain/source

## When you see this

- Logs: `Domain 'X' is paused (circuit breaker)` or `Source 'Y' blocked by circuit breaker`
- API/source discovery returns empty or errors for a specific provider (e.g. Semantic Scholar, arXiv)
- Telemetry: circuit state shows `open` for a key

## What it means

The circuit breaker has opened for that domain or source after too many failures in a short window (default: 5 failures in 60 seconds). New calls are rejected immediately to avoid cascading failures.

## What to check

1. **Telemetry** – `GET /telemetry/state` and look at `circuit_breakers` (or circuit state in your aggregator). Confirm which key is `open`.
2. **External status** – Check the provider’s status page (e.g. status.semanticscholar.org, arxiv.org) for outages or rate limits.
3. **Logs** – Search for the source/domain name and `record_source_failure` or `circuit` to see recent errors (timeouts, 429, 5xx).

## What to do

### Option A: Wait for automatic recovery

- After the recovery window (default 30 seconds), the circuit goes to **half-open** and one call is allowed. If it succeeds, the circuit **closes**; if it fails, it **opens** again.
- No action needed if the provider is back and the next probe succeeds.

### Option B: Manually reset (if you have an admin API)

- If your codebase exposes a way to reset a circuit (e.g. “reset circuit for source X”), use it only after confirming the provider is healthy.
- Otherwise, restart the app to clear in-memory circuit state (only if circuit state is not persisted).

### Option C: Adjust thresholds (optional)

- Env or config: failure threshold, window, recovery time (see `app/circuit_breaker.py`).
- Increase the failure threshold or window if the source is flaky but you want to tolerate more errors before opening.

## Prevention

- Keep rate limiting (per domain/source) so you don’t trigger provider 429s.
- Use retries with backoff for transient errors so only sustained failures open the circuit.

## Links

- Implementation: `app/circuit_breaker.py`
- Usage: `app/kg/source_discovery.py` (check before API calls, record success/failure)
