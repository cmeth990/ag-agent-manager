# Agent Swarm Constraints & Design Principles

When building or modifying agents in this system, ALWAYS ensure these requirements are met:

## Core Requirements (Must Answer YES)

1. **Output Validation**: Every agent output must be validated by code (schemas, Pydantic models)
2. **Safe Retries**: Every task must be idempotent and safely retriable
3. **Cost Caps**: Must be able to cap spend per domain/queue/day
4. **Provenance**: Every KG edge must have full provenance (source, agent, timestamp, reasoning)
5. **Rollback**: All KG changes must be reversible
6. **Duplication Detection**: Must detect duplicates and drift automatically
7. **Circuit Breakers**: Must be able to pause misbehaving domains/sources quickly
8. **Telemetry-Based State**: Supervisor must summarize state from telemetry, not chat memory

## Implementation Checklist

Before adding/modifying agents:
- [ ] Define output validation schema
- [ ] Implement idempotent retry logic
- [ ] Add cost tracking and caps
- [ ] Capture provenance metadata
- [ ] Add circuit breaker integration
- [ ] Use structured logging/telemetry
- [ ] Test failure modes and recovery

See `docs/AGENT_SWARM_DESIGN_PRINCIPLES.md` for detailed requirements.
