# Agent Guidelines

Each agent is built to these rules:

1. **Single responsibility** – One clear job per agent.
2. **Structured I/O** – JSON schema or function-call style; validate in code.
3. **Idempotency** – Safe to retry (upserts, no duplicate side effects).
4. **Deterministic guardrails** – Schema validation, allowlists, thresholds.
5. **Explicit provenance** – Every claim links back to evidence (sourceId/evidenceIds or SUPPORTS edges).

**If you do only one thing: force structured outputs and validate them in code.**

---

## Per-Agent Contract

### 1. Extractor (`extractor_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Extract entities, relations, and claims from user input (and optionally cheap verification first). |
| **Input** | `state["user_input"]` (string). |
| **Output** | `working_notes.extracted`: `{ entities, relations, claims }`. Entities: `id`, `label`, `properties`. Relations: `from`, `to`, `type`, `properties`. |
| **Structured I/O** | JSON: `entities[]`, `relations[]`, `claims[]`. Validated by `validate_extractor_output()`. |
| **Guardrails** | Node/edge allowlists (KG schema), max entities/relations/claims, max property length. |
| **Provenance** | Claims should have `sourceId` or `evidenceIds` in properties, or SUPPORTS edges from Evidence. If `REQUIRE_CLAIM_PROVENANCE=true`, Claims without evidence are filtered out (quarantined). |
| **Idempotency** | Same input → same output; downstream uses MERGE/upsert. |

### 2. Linker (`linker_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Deduplicate and link entities to canonical IDs. |
| **Input** | `working_notes.extracted` (entities, relations). |
| **Output** | `working_notes.linked`: `{ entities, relations, canonical_ids }`. |
| **Structured I/O** | Validated by `validate_linker_output()`. |
| **Guardrails** | Max linked entities/relations (thresholds). |
| **Idempotency** | Same extracted input → same canonical mapping; safe to retry. |

### 3. Writer (`writer_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Build `proposed_diff` from linked entities (nodes/edges add/update/delete). |
| **Input** | `working_notes.linked`, `user_input`. |
| **Output** | `proposed_diff`, `diff_id`, `approval_required=True`, `final_response`. |
| **Structured I/O** | Diff shape validated by `validate_writer_output()`. |
| **Guardrails** | Max nodes/edges per diff (add/update/delete). |
| **Idempotency** | Same linked input → same diff; commit is separate. |

### 4. Commit (`commit_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Apply approved diff to KG or handle reject. |
| **Input** | `proposed_diff`, `approval_decision` ("approve" | "reject"). |
| **Output** | State update: `proposed_diff`, `approval_required`, `final_response` (and optionally `error`). |
| **Structured I/O** | Validated by `validate_commit_output()`; keys must be in state allowlist; `approval_decision` in allowlist. |
| **Guardrails** | Allowlist of state keys; max response length. |
| **Idempotency** | `apply_diff` uses MERGE (idempotent writes). |

### 5. Query (`query_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Answer user query from KG (including fractal/ORP). |
| **Input** | `user_input` (query text). |
| **Output** | `final_response` (and optionally `error`). |
| **Structured I/O** | Validated by `validate_query_output()`; max response length. |
| **Guardrails** | State key allowlist, response length threshold. |

### 6. Source Gatherer (`source_gatherer_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Discover and rank sources for given domains. |
| **Input** | `user_input`, optional `discovered_sources`. |
| **Output** | `discovered_sources`: `{ domains, sources_by_domain, all_sources }`, optional `final_response`, `error`. |
| **Structured I/O** | Validated by `validate_source_gatherer_output()`. |
| **Guardrails** | Max domains/sources; source item must have `properties.title` or `properties.name`; numeric scores validated. |

### 7. Content Fetcher (`content_fetcher_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Fetch content from discovered sources (priority order). |
| **Input** | `user_input`, optional `discovered_sources`. |
| **Output** | `final_response` (and optionally `fetched_content`). |
| **Structured I/O** | LLM parse: JSON `{ domains, max_sources, min_priority }` validated by `validate_content_fetcher_parsed()`. |
| **Guardrails** | Max domains/sources per request; min_priority in [0,1]. |

### 8. Domain Scout (`domain_scout_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Scout for new domains from web/social. |
| **Input** | `user_input`, context. |
| **Output** | `scouting_results`, optional `final_response`, `error`. |
| **Structured I/O** | Validated by `validate_domain_scout_output()`. |

### 9. Improvement Agent (`improvement_agent_node`)

| Aspect | Contract |
|--------|----------|
| **Responsibility** | Propose code changes from user request. |
| **Input** | `user_input`. |
| **Output** | `proposed_changes` (path → content), `improvement_plan`, `final_response`, `error`. |
| **Structured I/O** | Validated by `validate_improvement_agent_output()`; `.py` paths only; max file size. |
| **Guardrails** | Allowlist of state keys; file path and content constraints. |

---

## Validation and Schemas

- **Allowlists**: `app/validation/schemas.py` – `INTENT_ALLOWLIST`, `APPROVAL_DECISION_ALLOWLIST`, `STATE_UPDATE_ALLOWLIST`, node/edge types from KG schema.
- **Thresholds**: `app/validation/schemas.Thresholds` – max entities, relations, sources, response length, etc.
- **Validators**: `app/validation/agent_outputs.py` – `validate_extractor_output`, `validate_linker_output`, `validate_writer_output`, `validate_commit_output`, `validate_query_output`, `validate_content_fetcher_parsed`, `validate_source_gatherer_output`, `validate_domain_scout_output`, `validate_improvement_agent_output`, `validate_agent_state_update`.

Validation is applied in code at the end of each agent (or to parsed LLM output). On failure, agents log and either use a sanitized/truncated result or raise so the graph can handle it.

---

## Provenance

- **Extraction prompt** instructs: every Claim must have `sourceId` or `evidenceIds`, or SUPPORTS edges from Evidence.
- **Validator** logs when a Claim has no evidence link. Optional enforcement: set `REQUIRE_CLAIM_PROVENANCE=true` to filter out (quarantine) Claims without provenance so they are not added to the KG.
- **KG apply** uses provenance from `enrich_diff_with_provenance()` so all new/updated nodes and edges carry source/reasoning metadata.

---

## Idempotency

- **Extractor/Linker/Writer**: Pure functions of state; no side effects until commit.
- **Commit**: `apply_diff` uses MERGE (upsert) in Neo4j; safe to retry.
- **Source/Content/Domain**: Read-only or cached; duplicate calls are safe.
- **Query**: Read-only.
