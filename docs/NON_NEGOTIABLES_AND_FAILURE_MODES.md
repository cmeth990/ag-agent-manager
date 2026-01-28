# Non-Negotiables and Failure Mode Handlers

## Non-Negotiables (All Implemented)

### 1. ✅ Durable queues (not in-memory)

**Module:** `app/queue/durable_queue.py`

- **Postgres-based task queue** - Tasks stored in `task_queue` table, survive restarts
- **Task states:** PENDING → IN_PROGRESS → COMPLETED/FAILED/DEAD_LETTER
- **Retry support:** Automatic retry with exponential backoff (via `app/retry.py`)
- **Usage:** `DurableTaskQueue.enqueue()`, `dequeue()`, `complete()`, `fail()`

**Note:** Currently LangGraph uses MemorySaver checkpointer (due to PostgresSaver bug), but task queue is Postgres-based.

### 2. ✅ Retries with exponential backoff + jitter

**Module:** `app/retry.py`

- **`retry_async(fn, max_retries=3, backoff_base=2.0, jitter=True)`** - Exponential backoff with random jitter
- **`@with_retry(...)`** decorator for async functions
- **Wired in:** API clients (`search_semantic_scholar`, `search_arxiv`, `search_openalex`, `search_wikipedia`) and LLM calls
- **Default:** 2 retries, 2.0s base, jitter enabled

### 3. ✅ Dead-letter queues + triage workflows

**Module:** `app/queue/triage.py`

- **Dead-letter queue:** Tasks that fail after max_retries are moved to `DEAD_LETTER` status
- **Triage actions:**
  - `retry`: Reset to PENDING for retry
  - `update_payload`: Update payload and retry
  - `skip`: Mark as skipped
- **API:** `GET /queue/dead-letter`, `POST /queue/triage/{task_id}?action=retry`

### 4. ✅ Heartbeats + "stuck task" detection

**Module:** `app/queue/heartbeat.py`

- **Heartbeat:** Tasks update `heartbeat_at` timestamp while IN_PROGRESS
- **Stuck detection:** Tasks with no heartbeat for 30+ minutes are flagged
- **Auto-retry:** Optional auto-retry of stuck tasks (if retry_count < max_retries)
- **API:** `GET /queue/stuck?threshold_minutes=30`
- **Background monitor:** `start_heartbeat_monitor()` runs periodic checks

### 5. ✅ Circuit breakers

**Module:** `app/circuit_breaker.py` (already implemented)

- Per-domain and per-source circuit breakers
- Automatic pause on error thresholds
- Wired into source discovery

### 6. ✅ Rate limiting per domain/source

**Module:** `app/queue/rate_limiter.py`

- **Per-source limits:** requests_per_minute, requests_per_hour
- **Per-domain limits:** Optional domain-specific limits
- **Default limits:** Semantic Scholar (100/min, 5000/hr), arXiv (10/min, 200/hr), etc.
- **Wired in:** All API clients check `check_rate_limit()` before requests, `record_request()` after
- **Enforcement:** Returns empty list if rate limited (doesn't fail)

### 7. ✅ Idempotent writes to KG

**Module:** `app/kg/idempotent.py`

- **MERGE pattern:** Uses Cypher `MERGE` instead of `CREATE` for nodes/edges
- **Upsert:** `ON CREATE SET ... ON MATCH SET ...` - creates if not exists, updates if exists
- **Wired in:** `apply_diff` uses `build_upsert_node_query()` and `build_upsert_edge_query()`
- **Safe retries:** Can retry same diff multiple times without creating duplicates

## Failure Mode Handlers

### 1. ✅ Source HTML changes → parser breaks

**Module:** `app/failure_modes/html_parser.py`

- **Graceful fallback:** `parse_html_with_fallback()` tries structured parsing, falls back to simple text extraction
- **Wired in:** `source_fetcher.fetch_source_content()` uses fallback parser
- **Degradation:** Simple → minimal fallback (strip tags only) if structured parsing fails

### 2. ✅ Paywalls appear

**Module:** `app/failure_modes/paywall.py`

- **Detection:** `detect_paywall(html, url)` checks for paywall indicators (keywords, services, HTML patterns)
- **Wired in:** `source_fetcher.fetch_source_content()` checks before parsing
- **Response:** Returns `accessible=False` with paywall metadata if detected

### 3. ✅ Robots/rate limits tighten

**Module:** `app/queue/rate_limiter.py` (see rate limiting above)

- Rate limits prevent overwhelming sources
- Circuit breakers pause sources on repeated failures
- Retries with backoff handle transient rate limit errors

### 4. ✅ Prompt injection / malicious pages

**Module:** `app/security/prompt_injection.py` (already implemented)

- All LLM calls wrap untrusted content
- Content sanitization strips scripts/hidden text

### 5. ✅ Model behavior shifts after upgrades

**Module:** `app/failure_modes/model_version.py`

- **Tracking:** `track_model_version(model_name, provider, version)` records model versions
- **Usage:** Track when model changes to detect behavior shifts
- **Future:** Could compare outputs across versions to detect drift

### 6. ✅ Silent duplication in entity resolution

**Module:** `app/kg/deduplication.py` (already implemented)

- Pre-insertion duplicate checks
- Semantic similarity matching
- Filters duplicates before apply

### 7. ✅ "Self-confirming loops" (agents cite each other)

**Module:** `app/failure_modes/circular_citation.py`

- **Detection:** `detect_circular_citations(diff)` finds cycles in citation graph (DFS)
- **Wired in:** `apply_diff` checks for circular citations before applying
- **Response:** Logs warnings for detected cycles (can optionally filter)

## Admin / telemetry auth

When `ADMIN_API_KEY` is set, these endpoints require authentication:

- **Header:** `X-Admin-Key: <key>` or `Authorization: Bearer <key>`
- **Module:** `app/auth.py` (dependency `require_admin_key`)

If `ADMIN_API_KEY` is not set, no check is performed (suitable for local dev). **In production, set `ADMIN_API_KEY`** so telemetry, queue, and KG admin are not publicly accessible.

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /telemetry/tasks` | Recent task states |
| `GET /telemetry/state` | Full system state |
| `GET /telemetry/summary` | Human-readable summary |
| `GET /kg/versions` | List KG versions |
| `GET /kg/versions/{version}` | Version details |
| `POST /kg/rollback/{target_version}` | Rollback KG |
| `GET /queue/dead-letter` | List tasks in dead-letter queue |
| `POST /queue/triage/{task_id}?action=retry` | Triage a DLQ task (retry/update/skip) |
| `GET /queue/stuck?threshold_minutes=30` | List stuck tasks (no heartbeat) |

## Runbooks

When something goes wrong, see [docs/runbooks/README.md](runbooks/README.md) for:

- **Circuit breaker open** – [RUNBOOK_CIRCUIT_BREAKER.md](runbooks/RUNBOOK_CIRCUIT_BREAKER.md)
- **Dead-letter queue** – [RUNBOOK_DLQ.md](runbooks/RUNBOOK_DLQ.md)
- **Budget exceeded** – [RUNBOOK_BUDGET_EXCEEDED.md](runbooks/RUNBOOK_BUDGET_EXCEEDED.md)
- **Stuck tasks** – [RUNBOOK_STUCK_TASKS.md](runbooks/RUNBOOK_STUCK_TASKS.md)

## Configuration

| Env var | Purpose |
|---------|---------|
| `DATABASE_URL` | Postgres connection for durable queue |
| `USE_DURABLE_QUEUE` | When `true`, webhook enqueues tasks and a background worker runs the graph (default: false) |
| `ADMIN_API_KEY` | If set, telemetry/queue/kg admin endpoints require this key via `X-Admin-Key` or `Authorization: Bearer <key>` |
| `QUEUE_STUCK_THRESHOLD_MINUTES` | Minutes without heartbeat = stuck (default: 30) |
| `QUEUE_AUTO_RETRY_STUCK` | Auto-retry stuck tasks (default: false) |

## Usage Examples

```python
# Enqueue a task
from app.queue.durable_queue import get_queue
queue = get_queue()
task_id = queue.enqueue("source_gathering", {"domain": "Algebra"}, domain="Algebra")

# Process task with heartbeat
task = queue.dequeue()[0]
queue.heartbeat(task.task_id)  # Send heartbeat while processing
# ... do work ...
queue.complete(task.task_id, result={"sources": [...]})

# Triage dead-letter task
from app.queue.triage import triage_dead_letter_task
await triage_dead_letter_task(task_id, action="retry")

# Monitor stuck tasks
from app.queue.heartbeat import monitor_stuck_tasks
result = await monitor_stuck_tasks(stuck_threshold_minutes=30, auto_retry=True)
```
