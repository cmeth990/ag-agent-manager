# ag-agent-manager: Architecture and Moving Parts

One document that describes all major components, flows, and where to find more detail.

---

## High-level architecture

```
Telegram → FastAPI (main.py) → LangGraph supervisor (graph/supervisor.py)
                                    ↓
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                     ↓
        Worker nodes          Durable queue          Admin/telemetry
   (extract, link, write,     (Postgres task         (auth, runbooks)
    gather, fetch, scout,      queue + worker)
    improve, query)
              ↓                     ↓
        KG client (Neo4j)     Cost / LLM tiering
        + source discovery    + validation
```

- **Entry:** Telegram webhook `POST /telegram/webhook` → `main.py` builds initial state, runs graph (or enqueues if `USE_DURABLE_QUEUE=true`).
- **Orchestration:** LangGraph in `app/graph/supervisor.py`: `detect_intent` → route to help, status, ingest, query, gather_sources, fetch_content, scout_domains, improve, graph_progress, push_changes, or extract→link→write (ingest).
- **Persistence:** Task queue in Postgres (`app/queue/`). LangGraph checkpointer is MemorySaver (in-memory); task queue is durable.
- **KG:** Neo4j via `app/kg/client.py`; source discovery and content fetching in `app/kg/`.

---

## Components (by area)

### Entry and API

| Component | Purpose | Module |
|-----------|---------|--------|
| FastAPI app | Webhook, health, admin/telemetry, KG progress dashboard | `app/main.py` |
| Telegram helpers | send_message, send_photo, answer_callback_query, build_approval_keyboard | `app/telegram.py` |
| Admin auth | Require `X-Admin-Key` or `Authorization: Bearer` when `ADMIN_API_KEY` set | `app/auth.py` |

### Graph and workers

| Component | Purpose | Module |
|-----------|---------|--------|
| Supervisor | Intent detection, routing, approval flow, build_graph | `app/graph/supervisor.py` |
| State | AgentState TypedDict (user_input, chat_id, intent, task_queue, proposed_diff, approval_*, etc.) | `app/graph/state.py` |
| Checkpointer | MemorySaver (PostgresSaver planned when fixed) | `app/graph/checkpoint.py` |
| Extractor | Extract concepts/claims from content; optional cheap path | `app/graph/workers.py` |
| Linker | Entity linking, dedup | `app/graph/workers.py` |
| Writer | Build proposed diff from linked state | `app/graph/workers.py` |
| Commit / Reject | apply_diff or discard; handle_reject | `app/graph/workers.py` |
| Query node | Natural language query over KG | `app/graph/workers.py` |
| Source gatherer | Discover sources for domain(s); LLM or fallback | `app/graph/source_gatherer.py` |
| Content fetcher | Fetch and rank content from discovered sources | `app/graph/content_fetcher.py` |
| Domain scout | Propose new domains from content | `app/graph/domain_scout_worker.py` |
| Improvement agent | Natural language → code change plan → propose edits → Approve/Reject | `app/graph/improvement_agent.py` |
| Push changes | Git push (e.g. to GitHub) after improvements approved | `app/graph/improvement_agent.py` |
| Graph progress node | Private link to KG progress dashboard (zoom by level) | `app/graph/supervisor.py` (graph_progress_node) |
| Parallel test node | Run gather + scout in parallel (test) | `app/graph/parallel_agents.py` |

### Knowledge graph (KG)

| Component | Purpose | Module |
|-----------|---------|--------|
| KG client | Neo4j driver, apply_diff, query_kg, idempotent upsert | `app/kg/client.py` |
| Idempotent writes | MERGE-based upsert for nodes/edges | `app/kg/idempotent.py` |
| Diff format | Normalize and format diffs | `app/kg/diff.py` |
| Schema / types | NODE_TYPES, EDGE_TYPES, schema summary for prompts | `app/kg/knowledge_base.py` |
| Hypernodes | create_hypernode, ORP structure, CONTAINS/NESTED_IN, expand_hypernode | `app/kg/hypernode.py` |
| Source discovery | discover_sources_for_domain; Semantic Scholar, arXiv, OpenAlex, Wikipedia, OpenStax, Khan, MIT OCW | `app/kg/source_discovery.py`, `app/kg/api_clients.py` |
| Source fetcher | Fetch content from URLs; rate limit, circuit breaker, HTML fallback | `app/kg/source_fetcher.py` |
| Domain taxonomy | DOMAIN_TAXONOMY, get_domain_by_name, create_domain_structure | `app/kg/domains.py` |
| Categories / upper ontology | CATEGORIES, UPPER_ONTOLOGY, category hypernodes | `app/kg/categories.py` |
| Scoring | Source quality, domain relevance, recency | `app/kg/scoring.py` |
| Rollback | List versions, rollback KG to version | `app/kg/rollback.py` |
| Progress | get_progress_stats, get_progress_tree, token create/validate, optional images | `app/kg/progress.py` |
| Audit trail / claim tiers | CLAIM_TIERS (Provisional/Supported/Audited), assign_confidence_tier, compute_p_error, enrich_claim_with_audit | `app/kg/audit_trail.py` |
| Dedup, provenance, versioning | Used in apply_diff or ingestion pipeline; provenance supports last_verified_at, evidence_summary | `app/kg/deduplication.py`, `app/kg/provenance.py`, `app/kg/versioning.py` |
| Domain scout (KG-side) | Domain extraction from text/candidates | `app/kg/domain_scout.py` |

### Queue and durability

| Component | Purpose | Module |
|-----------|---------|--------|
| Durable task queue | Postgres-backed enqueue/dequeue/complete/fail/heartbeat | `app/queue/durable_queue.py` |
| Worker | Background loop: dequeue graph_run, run graph, send Telegram response | `app/queue/worker.py` |
| Triage | List dead-letter tasks, retry/update_payload/skip | `app/queue/triage.py` |
| Heartbeat | Stuck-task detection, optional auto-retry | `app/queue/heartbeat.py` |
| Rate limiter | Per-source (and optional per-domain) limits; used by API clients | `app/queue/rate_limiter.py` |
| Retry | Exponential backoff + jitter; decorator and async helper | `app/retry.py` |

### Cost and LLM

| Component | Purpose | Module |
|-----------|---------|--------|
| LLM client | get_llm_base, get_llm, get_llm_for_agent (OpenAI/Anthropic) | `app/llm/client.py` |
| Tiering | get_llm_for_task (cheap/mid/expensive by task) | `app/llm/tiering.py` |
| Tracked client | Cost tracking, budget checks | `app/llm/tracked_client.py` |
| Budget envelopes | Per-task, per-agent/day, per-queue, per-tool caps | `app/cost/envelopes.py` |
| Budget / tracker | Daily budget, cost tracking | `app/cost/budget.py`, `app/cost/tracker.py` |
| Cache | Fetched docs, extraction results | `app/cost/cache.py` |
| Compression | Chunking, relevant-chunk retrieval, KG context compression | `app/cost/compression.py` |
| Cheap verification | should_use_llm, simple NER; bypass LLM when confident | `app/cost/cheap_verification.py` |

### Validation and security

| Component | Purpose | Module |
|-----------|---------|--------|
| Schemas / allowlists | INTENT_ALLOWLIST, node/edge allowlists, thresholds | `app/validation/schemas.py` |
| Agent output validators | validate_extractor_output, validate_linker_output, etc.; optional provenance filter | `app/validation/agent_outputs.py` |
| Circuit breaker | check_source_allowed, record_source_success/failure; per-domain/source | `app/circuit_breaker.py` |
| Security tools | require_tool, allowlist/blocklist for tools | `app/security/tools.py` |
| Prompt injection | wrap_untrusted_content | `app/security/prompt_injection.py` |
| Sanitize | sanitize_content, sanitize_for_llm (HTML/text for fetchers and LLM context) | `app/security/sanitize.py` |
| Network allowlist, anomaly, corroboration | Used in KG or ingestion | `app/security/network.py`, `app/security/anomaly.py`, `app/security/corroboration.py` |

### Failure modes

| Component | Purpose | Module |
|-----------|---------|--------|
| HTML parser fallback | Graceful fallback when structured parsing fails | `app/failure_modes/html_parser.py` |
| Paywall detection | Detect paywalled content | `app/failure_modes/paywall.py` |
| Circular citation | Detect citation cycles before apply_diff | `app/failure_modes/circular_citation.py` |
| Model version | Track model version for reproducibility | `app/failure_modes/model_version.py` |

### Telemetry and task state

| Component | Purpose | Module |
|-----------|---------|--------|
| Task state registry | In-memory recent task states (for supervisor/telemetry) | `app/task_state.py` |
| Telemetry aggregator | get_system_state, summarize_state (for /telemetry/state, /telemetry/summary) | `app/telemetry/aggregator.py` |

---

## Main flows

1. **Ingest:** User sends `/ingest topic=...` or “add knowledge about X” → extract → link → write → Approve/Reject → commit (or reject). Uses durable queue when `USE_DURABLE_QUEUE=true`.
2. **Gather sources:** `/gather sources for <domain>` → source_gatherer → discover_sources_for_domain (academic + educational + general APIs) → formatted response.
3. **Fetch content:** `/fetch content for <domain>` → content_fetcher → fetch and rank content from discovered sources.
4. **Query:** `/query <question>` → query_node → KG query.
5. **Scout domains:** `/scout domains` → domain_scout_node.
6. **Improve:** “Improve the source gatherer …” or `/improve …` → improvement_agent → plan → propose edits → Approve/Reject → apply or reject.
7. **Graph progress:** `/graph` or “graph progress” → graph_progress_node → private link to `/graph/progress?token=...` (drill-down by level).
8. **Push changes:** “Push to GitHub” after improvements → push_changes_node.
9. **Approval:** Any node can set `approval_required`; user taps Approve/Reject → callback → graph continues with `approval_decision`.

---

## Configuration (env vars)

| Var | Purpose |
|-----|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token (required for Telegram). |
| `DATABASE_URL` | Postgres (queue, and checkpointer when PostgresSaver used). |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j (required for KG). |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | At least one for LLM. |
| `USE_DURABLE_QUEUE` | If `true`, webhook enqueues and worker runs graph. |
| `ADMIN_API_KEY` | If set, admin/telemetry endpoints require this key. |
| `PUBLIC_URL` or `RAILWAY_URL` | Base URL for graph progress link. |
| `GRAPH_VIEW_SECRET` | Optional; for progress link signing (else uses `ADMIN_API_KEY`). |
| `REQUIRE_CLAIM_PROVENANCE` | If `true`, filter claims without evidence. |
| Cost-related | `LLM_DAILY_BUDGET_USD`, `COST_PER_TASK_CAP_USD`, etc. (see [COST_CONTROL.md](COST_CONTROL.md)). |
| Queue-related | `QUEUE_STUCK_THRESHOLD_MINUTES`, `QUEUE_AUTO_RETRY_STUCK`. |

---

## API endpoints (summary)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /`, `GET /health` | None | Health. |
| `POST /telegram/webhook` | None | Telegram updates. |
| `GET /graph/progress?token=...` | Token in URL | Private KG progress dashboard (HTML). |
| `GET /graph/progress/data?token=...` | Token in URL | Progress tree JSON. |
| `GET /telemetry/tasks`, `/telemetry/state`, `/telemetry/summary` | Admin key | Telemetry. |
| `GET /kg/versions`, `GET /kg/versions/{id}`, `POST /kg/rollback/{id}` | Admin key | KG versions and rollback. |
| `GET /queue/dead-letter`, `POST /queue/triage/{task_id}`, `GET /queue/stuck` | Admin key | Queue and triage. |

---

## Where to read more

- **Audit trail and claim tiers:** [AUDIT_TRAIL_AND_CLAIM_TIERS.md](AUDIT_TRAIL_AND_CLAIM_TIERS.md) — spec mapping (audit_trail_process.pdf), claim tiers (Provisional/Supported/Audited), P(error), evidence edges (SUPPORTS/REFUTES/QUALIFIES/ANCHORS), provenance, pipeline.
- **Runbooks (ops):** [docs/runbooks/README.md](runbooks/README.md) — circuit breaker, DLQ, budget exceeded, stuck tasks.
- **Non-negotiables and failure modes:** [NON_NEGOTIABLES_AND_FAILURE_MODES.md](NON_NEGOTIABLES_AND_FAILURE_MODES.md) — queue, retries, DLQ, heartbeats, circuit breaker, rate limit, idempotent KG, failure handlers.
- **Cost control:** [COST_CONTROL.md](COST_CONTROL.md) — budgets, tiering, cache, compression, cheap verification.
- **Agent guidelines:** [AGENT_GUIDELINES.md](AGENT_GUIDELINES.md) — schemas, validation, provenance, idempotency.
- **Conversational improve + expand KG:** [CONVERSATIONAL_IMPROVE_AND_KG.md](CONVERSATIONAL_IMPROVE_AND_KG.md) — improve agents and expand KG via chat.
- **Deploy (Railway):** [../RAILWAY_DEPLOY_CHECKLIST.md](../RAILWAY_DEPLOY_CHECKLIST.md), [../VERIFY_RAILWAY.md](../VERIFY_RAILWAY.md).
- **Testing:** [../TESTING_GUIDE.md](../TESTING_GUIDE.md), `pytest tests/`.

---

## Quick reference: where is X?

- **Intent routing / new command:** `app/graph/supervisor.py` (`detect_intent`, `route_after_intent`).
- **New worker node:** Add node in `supervisor.py`, implement in `app/graph/` or `app/kg/`.
- **New KG source or API:** `app/kg/source_discovery.py`, `app/kg/api_clients.py`; wire rate limit and circuit breaker.
- **New validation rule:** `app/validation/schemas.py`, `app/validation/agent_outputs.py`.
- **Claim tier / P(error):** `app/kg/audit_trail.py` (`assign_confidence_tier`, `enrich_claim_with_audit`); wire after `calculate_claim_confidence` in ingestion.
- **Admin/telemetry auth:** `app/auth.py`; protect new route with `Depends(require_admin_key)`.
- **Cost / tiering:** `app/llm/tiering.py`, `app/cost/envelopes.py`.
