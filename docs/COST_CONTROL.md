# Cost Control: Budget Envelopes, Model Tiering, Caching, Compression, and Cheap Verification

## Overview

Comprehensive cost control system with layered defenses to prevent "death by a thousand paper cuts" from token burn.

## A) Budget Envelopes Everywhere

**Module:** `app/cost/envelopes.py`

Multiple budget caps at different scopes:

### Per-Task Token Cap
- **Env var:** `COST_PER_TASK_CAP_USD`
- **Scope:** Single task (all time)
- **Usage:** Prevents any single task from exceeding budget

### Per-Agent/Day Cap
- **Env var:** `COST_PER_AGENT_DAILY_CAP_USD`
- **Scope:** Agent per day
- **Usage:** Limits daily spend per agent (e.g., source_gatherer, extractor)

### Per-Domain/Day Cap
- **Already implemented** in `app/cost/budget.py`
- **Scope:** Domain per day
- **Usage:** Limits daily spend per domain

### Per-Queue Concurrency Cap
- **Env var:** `COST_PER_QUEUE_CONCURRENCY_CAP_USD`
- **Scope:** Per concurrent task in queue
- **Usage:** Limits cost per concurrent task (prevents queue overload)

### Per-Tool Call Cap
- **Env var:** `COST_PER_TOOL_CALL_CAP_USD`
- **Scope:** Single tool call (e.g., search, crawl)
- **Usage:** Prevents expensive tool calls

### When a Cap is Hit

The system can:
1. **Downgrade model** - Switch to cheaper tier (see Model Tiering)
2. **Reduce context window** - Use context compression (see Compression)
3. **Sample fewer candidates** - Filter to high-impact only (see Cheap Verification)
4. **Defer to next window** - Move task to next time window
5. **Require human review** - Flag for manual approval

**Implementation:** `EnvelopeManager.enforce_all_caps()` checks all applicable caps before LLM calls.

## B) Model Tiering (Critical)

**Module:** `app/llm/tiering.py`

Use smaller/cheaper models for simple tasks, bigger for complex.

### Tier Mapping

| Task Type | Tier | Model (OpenAI) | Model (Anthropic) |
|-----------|------|----------------|-------------------|
| **Cheap Tier** | | | |
| triage | Cheap | gpt-4o-mini | claude-3-haiku |
| classification | Cheap | gpt-4o-mini | claude-3-haiku |
| dedupe_suggestion | Cheap | gpt-4o-mini | claude-3-haiku |
| extraction_draft | Cheap | gpt-4o-mini | claude-3-haiku |
| source_filtering | Cheap | gpt-4o-mini | claude-3-haiku |
| simple_extraction | Cheap | gpt-4o-mini | claude-3-haiku |
| **Mid Tier** | | | |
| extraction | Mid | gpt-4o | claude-3-sonnet |
| entity_linking | Mid | gpt-4o | claude-3-sonnet |
| source_scoring | Mid | gpt-4o | claude-3-sonnet |
| domain_scouting | Mid | gpt-4o | claude-3-sonnet |
| **Expensive Tier** | | | |
| ontology_placement | Expensive | gpt-4-turbo | claude-3-opus |
| contradiction_resolution | Expensive | gpt-4-turbo | claude-3-opus |
| complex_disambiguation | Expensive | gpt-4-turbo | claude-3-opus |
| multi_source_synthesis | Expensive | gpt-4-turbo | claude-3-opus |
| evidence_synthesis | Expensive | gpt-4-turbo | claude-3-opus |

### Usage

```python
from app.llm.tiering import get_llm_for_task

# Get appropriate model for task
llm = get_llm_for_task("triage", domain="Algebra", agent="source_gatherer")
# Returns: gpt-4o-mini (cheap tier)

llm = get_llm_for_task("ontology_placement", domain="Algebra", agent="linker")
# Returns: gpt-4-turbo (expensive tier)
```

### Configuration

Override model selection via env vars:
- `OPENAI_MODEL_CHEAP` (default: gpt-4o-mini)
- `OPENAI_MODEL_MID` (default: gpt-4o)
- `OPENAI_MODEL_EXPENSIVE` (default: gpt-4-turbo)
- `ANTHROPIC_MODEL_CHEAP` (default: claude-3-haiku-20240307)
- `ANTHROPIC_MODEL_MID` (default: claude-3-sonnet-20240229)
- `ANTHROPIC_MODEL_EXPENSIVE` (default: claude-3-opus-20240229)

## C) Caching and Memoization

**Module:** `app/cost/cache.py`

Cache expensive operations to avoid redundant LLM calls.

### Cached Items

| Cache Type | TTL | Description |
|------------|-----|-------------|
| `fetched_doc` | 24h | Fetched documents and cleaned text |
| `cleaned_text` | 24h | Sanitized text content |
| `embedding` | 7d | Vector embeddings |
| `source_score` | 1h | Source quality scores |
| `extraction_result` | 24h | LLM extraction results (keyed by doc hash + schema version) |

### Usage

```python
from app.cost.cache import get_cache, cached

# Manual caching
cache = get_cache()
cached_value = cache.get("extraction_result", user_input=text)
if not cached_value:
    result = await expensive_extraction(text)
    cache.set("extraction_result", result, user_input=text)

# Decorator
@cached("extraction_result", ttl_seconds=86400)
async def extract_entities(text: str) -> Dict:
    # Expensive extraction
    return result
```

### Cache Key Generation

Cache keys are generated from:
- Cache type
- Function arguments (args, kwargs)
- SHA256 hash for consistent keys

## D) Context Compression

**Module:** `app/cost/compression.py`

Reduce token usage by only sending relevant context.

### Features

1. **Document Chunking**
   - Split long documents into overlapping chunks
   - Default: 2000 chars per chunk, 200 char overlap

2. **Relevant Chunk Retrieval**
   - Retrieve only top-k most relevant chunks for query
   - Simple keyword matching (can be enhanced with embeddings)

3. **Domain Briefs**
   - Maintain small summaries per domain
   - Include key concepts
   - Max 500 chars for LLM context

4. **KG Context Compression**
   - Retrieve only neighborhood subgraph (not entire KG)
   - Limit to max_nodes (default: 10)

### Usage

```python
from app.cost.compression import chunk_text, retrieve_relevant_chunks, get_domain_brief

# Chunk document
chunks = chunk_text(long_document, chunk_size=2000, overlap=200)

# Retrieve relevant chunks
relevant = retrieve_relevant_chunks(query, chunks, top_k=3)

# Get domain brief
brief = get_domain_brief("Algebra")
context = brief.get_context(max_length=500)
```

## E) Cheap Verification Before Expensive Reasoning

**Module:** `app/cost/cheap_verification.py`

Run regex/NER/statistical extraction first, only send uncertain cases to LLMs.

### Features

1. **Simple NER**
   - Extract dates, numbers, URLs, emails, proper nouns
   - No LLM required

2. **Statistical Extraction**
   - Extract frequent terms/phrases
   - Word frequency analysis

3. **Confidence-Based Routing**
   - `should_use_llm(text, confidence_threshold=0.7)` decides if LLM needed
   - High confidence → use cheap extraction
   - Low confidence → use LLM

4. **High-Impact Filtering**
   - `filter_high_impact_candidates()` filters before expensive validation
   - Criteria: confidence, source count, recency, domain relevance

### Usage

```python
from app.cost.cheap_verification import should_use_llm, simple_ner, filter_high_impact_candidates

# Check if LLM needed
use_llm, confidence, cheap_results = should_use_llm(text, confidence_threshold=0.7)

if not use_llm:
    # Use cheap extraction
    ner = cheap_results["ner"]
    stats = cheap_results["statistics"]
else:
    # Use LLM
    result = await llm_extract(text)

# Filter candidates before expensive validation
high_impact = filter_high_impact_candidates(candidates, max_candidates=10)
```

### Integration

**Wired into:** `app/graph/workers.py` - `extractor_node()`
- Checks `should_use_llm()` before LLM extraction
- Uses cheap extraction if confidence is high
- Caches results to avoid redundant calls

## Configuration Summary

| Env Var | Purpose | Default |
|---------|---------|---------|
| `COST_PER_TASK_CAP_USD` | Per-task budget cap | None |
| `COST_PER_AGENT_DAILY_CAP_USD` | Per-agent daily cap | None |
| `COST_PER_QUEUE_CONCURRENCY_CAP_USD` | Per-queue concurrency cap | None |
| `COST_PER_TOOL_CALL_CAP_USD` | Per-tool call cap | None |
| `OPENAI_MODEL_CHEAP` | Cheap tier model | gpt-4o-mini |
| `OPENAI_MODEL_MID` | Mid tier model | gpt-4o |
| `OPENAI_MODEL_EXPENSIVE` | Expensive tier model | gpt-4-turbo |
| `ANTHROPIC_MODEL_CHEAP` | Cheap tier model | claude-3-haiku-20240307 |
| `ANTHROPIC_MODEL_MID` | Mid tier model | claude-3-sonnet-20240229 |
| `ANTHROPIC_MODEL_EXPENSIVE` | Expensive tier model | claude-3-opus-20240229 |

## Cost Savings Examples

1. **Cheap Verification:** 70% of extractions use regex/NER instead of LLM → **70% cost reduction**
2. **Model Tiering:** Use gpt-4o-mini for triage instead of gpt-4-turbo → **10x cost reduction**
3. **Caching:** Cache extraction results → **100% cost reduction for repeated queries**
4. **Context Compression:** Send 500 chars instead of 5000 → **90% token reduction**
5. **Budget Envelopes:** Prevent runaway costs → **Hard cap protection**

## Integration Points

- **LLM Calls:** `app/llm/tracked_client.py` - Enforces envelope caps
- **Extraction:** `app/graph/workers.py` - Uses cheap verification + tiering
- **Source Fetching:** `app/kg/source_fetcher.py` - Caches fetched docs
- **All Agents:** Can use `get_llm_for_task()` for tiered model selection
