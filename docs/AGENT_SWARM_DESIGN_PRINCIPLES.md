# Agent Swarm Design Principles

## Core Questions & Requirements

These are the fundamental questions that must be answered "YES" for every agent and feature in the swarm:

### 1. **Can every agent output be validated by code?**
**Requirement:** All agent outputs must be programmatically verifiable.
- ✅ Use structured outputs (JSON, schemas)
- ✅ Implement validation functions for each agent type
- ✅ Reject invalid outputs before processing
- ❌ Never trust unstructured LLM output without validation

**Implementation:**
- Define output schemas for each agent
- Use Pydantic models or JSON Schema validation
- Validate before storing in KG or committing changes

### 2. **Can every task be retried safely?**
**Requirement:** All operations must be idempotent and safe to retry.
- ✅ Use idempotent operations (check before create, upsert patterns)
- ✅ Track task state (pending, in_progress, completed, failed)
- ✅ Support checkpointing and resume
- ❌ Never assume operations are atomic or one-time

**Implementation:**
- Use task queues with state tracking
- Implement retry logic with exponential backoff
- Store intermediate results for resume capability
- Use database transactions where possible

### 3. **Can you cap spend per domain/queue/day?**
**Requirement:** Cost controls must be enforceable at granular levels.
- ✅ Track LLM API costs per domain, queue, and day
- ✅ Implement hard caps that stop execution when exceeded
- ✅ Provide cost visibility and alerts
- ❌ Never allow unbounded spending

**Implementation:**
- Cost tracking middleware for all LLM calls
- Budget limits per domain/queue with enforcement
- Daily/weekly/monthly budget caps
- Cost alerts before hitting limits

### 4. **Can you explain every KG edge with provenance?**
**Requirement:** Full traceability for all knowledge graph relationships.
- ✅ Store source, timestamp, agent, and confidence for every edge
- ✅ Track the reasoning/evidence that created each relationship
- ✅ Support "why does this edge exist?" queries
- ❌ Never create edges without provenance metadata

**Implementation:**
- Enrich all KG edges with provenance fields:
  - `source_agent`: Which agent created it
  - `source_document`: Original source URL/ID
  - `created_at`: Timestamp
  - `confidence`: Confidence score
  - `reasoning`: LLM reasoning or extraction method
  - `evidence`: Supporting text/quotes

### 5. **Can you roll back graph changes?**
**Requirement:** All KG modifications must be reversible.
- ✅ Version control for KG changes
- ✅ Store change history (what was added/removed/modified)
- ✅ Support rollback to previous state
- ❌ Never make destructive changes without backup

**Implementation:**
- Store KG changes in a changelog/audit table
- Implement versioning (snapshots or incremental)
- Provide rollback commands/API
- Test rollback procedures regularly

### 6. **Can you detect duplication and drift automatically?**
**Requirement:** System must identify redundant or conflicting information.
- ✅ Detect duplicate nodes/edges (same content, different IDs)
- ✅ Identify semantic drift (same concept, different representations)
- ✅ Flag contradictions (conflicting facts about same entity)
- ❌ Never silently create duplicates or ignore conflicts

**Implementation:**
- Deduplication checks before insertion
- Semantic similarity matching
- Conflict detection algorithms
- Automated merge/resolution strategies
- Regular drift detection scans

### 7. **Can you pause a misbehaving domain/source quickly?**
**Requirement:** Circuit breakers and kill switches must be immediate.
- ✅ Circuit breakers per domain/source
- ✅ Ability to pause/resume agents instantly
- ✅ Automatic pause on error thresholds
- ❌ Never allow runaway agents to continue

**Implementation:**
- Health monitoring per domain/source
- Circuit breaker pattern (open/closed/half-open states)
- Kill switch API/command
- Automatic pause on:
  - High error rates
  - Cost threshold exceeded
  - Quality degradation
  - Security violations

### 8. **Can your supervisor summarize state from telemetry (not chat memory)?**
**Requirement:** System state must be observable via structured telemetry.
- ✅ Structured logging and metrics
- ✅ Telemetry-based state summarization
- ✅ Health dashboards from metrics
- ❌ Never rely solely on conversational memory for state

**Implementation:**
- Structured logging (JSON logs with consistent schema)
- Metrics collection (Prometheus/StatsD compatible)
- Telemetry endpoints for state queries
- Supervisor can query:
  - Agent health status
  - Queue depths
  - Cost tracking
  - Error rates
  - Processing rates
  - KG statistics

## Design Implications

### Architecture Requirements

1. **Validation Layer**: Every agent must have a validation function
2. **Retry Infrastructure**: Task queue with state management
3. **Cost Tracking**: Middleware that tracks and enforces budgets
4. **Provenance System**: Metadata storage for all KG operations
5. **Version Control**: KG change tracking and rollback capability
6. **Deduplication Engine**: Pre-insertion checks and conflict detection
7. **Circuit Breakers**: Per-domain/source health monitoring and controls
8. **Telemetry System**: Structured logging and metrics collection

### Current State Assessment

**✅ Already Implemented:**
- Basic error handling and retries (some agents)
- Cost tracking (partial - LLM calls tracked but not enforced)
- Structured outputs (some agents use JSON)
- Logging (basic structured logging exists)

**❌ Missing/Incomplete:**
- Comprehensive output validation for all agents
- Idempotent retry infrastructure
- Cost caps and enforcement
- Full provenance tracking for KG edges
- KG versioning and rollback
- Automatic duplication/drift detection
- Circuit breakers per domain/source
- Telemetry-based state summarization

## Implementation Priority

1. **High Priority** (Security & Reliability):
   - Output validation for all agents
   - Circuit breakers and kill switches
   - Provenance tracking for KG edges

2. **Medium Priority** (Cost & Quality):
   - Cost caps and enforcement
   - Duplication/drift detection
   - Safe retry infrastructure

3. **Lower Priority** (Operational Excellence):
   - KG versioning and rollback
   - Telemetry-based state summarization

## Checklist for New Agents

Before adding any new agent, verify:

- [ ] Output validation schema defined
- [ ] Retry logic implemented (idempotent operations)
- [ ] Cost tracking integrated
- [ ] Provenance metadata captured (if creating KG edges)
- [ ] Circuit breaker integration
- [ ] Structured logging/telemetry
- [ ] Error handling and recovery
- [ ] Test coverage for failure modes

## References

- Original design questions from: `KG - Agent Swarm + Supervisor - Agnosia.pdf`
- Related: Cost control, Non-negotiables, Common failure modes, Security & data integrity
