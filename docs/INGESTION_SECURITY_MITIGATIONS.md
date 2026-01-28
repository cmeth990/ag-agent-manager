# Ingestion Agent Security Mitigations

Practical mitigations implemented for ingestion agents, in priority order.

## 1. Tool sandboxing

**Agents can't run arbitrary code; only approved tools.**

- **Module:** `app/security/tools.py`
- **Approved tools (default):** `llm_invoke`, `http_get`, `kg_query`, `kg_apply_diff`, `file_read`, `file_write`, `git_add_commit`
- **Blocked:** `eval`, `exec`, `subprocess`, `os.system`, `shell`, etc.
- **Usage:** Improvement agent calls `require_tool("file_write")` and `require_tool("git_add_commit")` before file/git operations; unapproved tools raise `SecurityError`.
- **Config:** `SECURITY_APPROVED_TOOLS` (comma-separated) to add tools; `SECURITY_BLOCKED_TOOLS` to block.

## 2. Network egress controls

**Allowlist domains for crawling; only those hosts can be fetched.**

- **Module:** `app/security/network.py`
- **Default allowlist:** Semantic Scholar, arXiv, OpenAlex, Wikipedia, OpenStax, Khan Academy, MIT OCW, Reddit, etc.
- **Usage:** `source_fetcher.fetch_source_content()` and `domain_scout.scout_web_source()` check `is_url_allowed(url)` before any HTTP request; non-allowlisted URLs are blocked.
- **Config:** `SECURITY_NETWORK_ALLOWLIST` (comma-separated) to add domains.

## 3. Content sanitization

**Strip scripts, ignore hidden text tricks.**

- **Module:** `app/security/sanitize.py`
- **Actions:** Strip script/style/iframe/object/embed/form tags; remove HTML comments; remove zero-width/invisible Unicode; remove `data:`/`javascript:` URIs; remove `on*` event handlers; strip CSS that hides text (e.g. `display:none`).
- **Usage:** Fetched HTML is passed through `sanitize_content(..., content_type="html")` in `source_fetcher` and `domain_scout` before use.

## 4. Prompt injection defenses

**Treat retrieved text as untrusted data; never let it override system instructions.**

- **Module:** `app/security/prompt_injection.py`
- **Mechanism:** `wrap_untrusted_content(text)` wraps user/retrieved content in delimiters and a prefix instructing the model to treat it as data only and not follow instructions within it.
- **Usage:** All LLM calls wrap untrusted content:
  - Extractor node: `wrap_untrusted_content(user_input)`
  - Source gatherer: `wrap_untrusted_content(user_input)`
  - Content fetcher: `wrap_untrusted_content(user_input)`
  - Domain scout: `wrap_untrusted_content(sanitized_html/text)` for fetched content

## 5. Cross-source corroboration

**Require 2+ independent sources for key facts (Claim nodes / DEFINES/SUPPORTS edges).**

- **Module:** `app/security/corroboration.py`
- **Functions:** `require_corroboration(nodes, edges, min_sources=2, require_for_claims_only=True)` returns allowed/flagged/errors; `filter_diff_by_corroboration(diff, ...)` returns a diff with insufficiently corroborated items removed.
- **Usage:** Wired into `apply_diff` (optional, enabled via `SECURITY_REQUIRE_CORROBORATION=true`). When enabled, filters out Claim nodes and DEFINES/SUPPORTS edges that don't have 2+ independent sources. Currently provenance is single-source per node; module is ready for multi-source ingestion.

## 6. Provenance-first

**Every edge has evidence pointers.**

- **Existing:** `app/kg/provenance.py` and `enrich_diff_with_provenance()` in the writer node attach `_provenance` (source_agent, source_document, created_at, reasoning) to all nodes/edges in a diff before commit.
- **Usage:** All KG writes go through the writer node, which calls `enrich_diff_with_provenance()`; no change required.

## 7. Anomaly detection

**Sudden surge of new concepts from one domain = suspicious.**

- **Module:** `app/security/anomaly.py`
- **Mechanism:** `record_ingestion(domain, count)` records ingestions per domain; `check_ingestion_anomaly(domain, proposed_add_count, surge_threshold=50, window_minutes=60)` flags if (current + proposed) in window exceeds threshold.
- **Usage:** `apply_diff` calls `check_ingestion_anomaly` before applying and `record_ingestion` after successful apply; anomalies are logged as warnings.

## Configuration summary

| Env var | Purpose |
|---------|---------|
| `SECURITY_APPROVED_TOOLS` | Comma-separated list of additional approved tools |
| `SECURITY_BLOCKED_TOOLS` | Comma-separated list of tools to block |
| `SECURITY_NETWORK_ALLOWLIST` | Comma-separated list of domains to allow for fetch |
| `SECURITY_REQUIRE_CORROBORATION` | Set to `"true"` to enable 2+ source requirement for Claim nodes (default: `"false"`) |

## File touchpoints

- **Tool sandboxing:** `app/graph/improvement_agent.py` (file_write, git_add_commit)
- **Network allowlist:** `app/kg/source_fetcher.py`, `app/kg/domain_scout.py`
- **Content sanitization:** `app/kg/source_fetcher.py`, `app/kg/domain_scout.py`
- **Prompt injection:** `app/graph/workers.py` (extractor_node), `app/graph/source_gatherer.py`, `app/graph/content_fetcher.py`, `app/kg/domain_scout.py` (all LLM calls)
- **Anomaly:** `app/kg/client.py` (apply_diff)
- **Provenance:** `app/graph/workers.py` (writer_node, existing)
- **Corroboration:** `app/kg/client.py` (apply_diff, optional via `SECURITY_REQUIRE_CORROBORATION=true`)
