# End-to-end system status

**Short answer:** The **code path** is wired end-to-end (Telegram webhook → FastAPI → LangGraph → workers → KG/queue/telemetry), and **unit/integration tests** cover most components. Full **live** e2e (real Telegram → real Neo4j/Postgres) depends on env and services; there is **no automated e2e test** that runs the full pipeline in one go.

---

## 1. Code path (is the pipeline wired?)

| Stage | Status | Where |
|-------|--------|--------|
| **Entry** | ✅ | `POST /telegram/webhook` → parse update → build `AgentState` |
| **Orchestration** | ✅ | `run_graph(initial_state, thread_id)` → supervisor → `detect_intent` → `route_after_intent` → node (help, ingest, query, gather_sources, fetch_content, scout_domains, improve, graph_progress, push_changes, etc.) |
| **Durable queue** | ✅ | If `USE_DURABLE_QUEUE=true` and `DATABASE_URL` set: webhook enqueues; background worker dequeues and runs graph, then sends Telegram response |
| **Inline** | ✅ | If queue off: graph runs inline after webhook; result sent via `send_message` / `answer_callback_query` |
| **Workers** | ✅ | Extractor, linker, writer, commit/reject, query, source_gatherer, content_fetcher, domain_scout, improvement_agent, graph_progress_node all connected in graph |
| **KG** | ✅ | Neo4j client, apply_diff, source discovery, scoring, audit trail, progress tree; idempotent writes, provenance |
| **Telemetry / admin** | ✅ | `/health`, `/telemetry/*`, `/kg/versions`, `/queue/*` (with admin key when `ADMIN_API_KEY` set) |

So **yes**: the system is **wired** end-to-end. A request can flow: Telegram → webhook → graph → node(s) → KG or queue → Telegram response.

---

## 2. Tests

| Scope | Count | Notes |
|-------|--------|------|
| **Unit / integration** | **50 passing** | Audit trail, cost envelopes, queue rate limiter, validation (schemas, agent outputs). Run: `pytest tests/ --ignore=tests/test_ingest_path.py` |
| **Ingest path** | 2 tests | `test_ingest_path.py` (linker_node, writer_node) **requires** `pytest-asyncio` installed and configured; otherwise collection or run can fail. |
| **E2E** | **0** | No test that: POSTs to `/telegram/webhook` with a fake update → runs graph → asserts Telegram send or final state. |

So **unit/integration**: most components are tested. **Full pipeline in one test**: not implemented.

---

## 3. What’s required for a “live” e2e run

For a **real** end-to-end run (you send a message in Telegram and get a response):

| Requirement | Purpose |
|-------------|---------|
| **TELEGRAM_BOT_TOKEN** | Bot API; webhook must be set to your app URL |
| **Webhook URL** | Telegram sends updates to `https://your-domain/telegram/webhook` |
| **Neo4j** (optional for some intents) | KG reads/writes for ingest, query, progress; help/gather/fetch can run without Neo4j for discovery/fetch only |
| **OPENAI_API_KEY or ANTHROPIC_API_KEY** | LLM for extractor, source_gatherer (query expansion), content_fetcher, domain_scout, improvement_agent; without it, some nodes fall back to non-LLM behavior or fail |
| **DATABASE_URL** (optional) | Postgres for durable queue and (when enabled) checkpointer; without it, queue is disabled and graph runs inline |
| **PUBLIC_URL or RAILWAY_URL** | For graph progress link in Telegram |

So **“is it working end-to-end?”** in production: **yes, provided** the env and services above are set and the webhook is registered. The code path is complete; failures are usually env (missing key, rate limit, Neo4j/Postgres down).

---

## 4. Gaps

1. **No automated e2e test** — Add a test (or script) that: POSTs a minimal Telegram update to `/telegram/webhook`, runs the app (or TestClient), and asserts that the graph runs and either a Telegram send is mocked or `final_response` / state is as expected.
2. **Ingest path tests** — Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` (or equivalent) is set so `test_ingest_path.py` runs without “async functions not natively supported”.
3. **Postgres checkpointer** — LangGraph still uses MemorySaver; when `langgraph-checkpoint-postgres` is fixed, switch to PostgresSaver for persistence across restarts.

---

## 5. Quick verification

- **Health:** `curl https://your-app/health` → `{"status":"healthy"}`.
- **Help (live):** In Telegram, send `/help` → bot replies with command list.
- **Gather (live):** Send “gather sources for Algebra” → bot replies with discovered sources (may be rate-limited or need LLM key for best results).
- **Tests (no e2e):**  
  `cd ag-agent-manager && pip install pytest-asyncio && pytest tests/ -v`

---

**Summary:** The system **is** working end-to-end in code: webhook → graph → workers → KG/queue → response. Unit/integration tests pass for the majority of components. There is no single automated e2e test; live e2e depends on configuration and external services (Telegram, optional Neo4j/Postgres, LLM keys).
