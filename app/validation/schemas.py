"""
Structured I/O schemas, allowlists, and thresholds for all agents.
Every agent has: single responsibility, structured I/O, deterministic guardrails.
"""
from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# Allowlists (deterministic guardrails)
# ---------------------------------------------------------------------------

# Valid intents (supervisor routing)
INTENT_ALLOWLIST = frozenset({
    "ingest", "query", "update", "source_gather", "content_fetch",
    "domain_scout", "improve", "status", "help", "unknown",
    "gather_sources", "fetch_content", "scout_domains", "parallel_test",
    "cancel", "push_changes",
})

# Valid approval decisions
APPROVAL_DECISION_ALLOWLIST = frozenset({"approve", "reject"})

# Node labels must be in KG schema (see knowledge_base.NODE_TYPES)
# Edge types must be in KG schema (see knowledge_base.EDGE_TYPES)
# Import at runtime to avoid circular deps
def get_node_type_allowlist() -> frozenset:
    from app.kg.knowledge_base import NODE_TYPES
    return frozenset(NODE_TYPES.keys())

def get_edge_type_allowlist() -> frozenset:
    from app.kg.knowledge_base import EDGE_TYPES
    return frozenset(EDGE_TYPES.keys())

# Claim types (for Claim nodes)
CLAIM_TYPE_ALLOWLIST = frozenset({
    "definition", "empirical", "theoretical", "operationalization",
    "misconception", "relation", "other"
})

# ---------------------------------------------------------------------------
# Thresholds (guardrails)
# ---------------------------------------------------------------------------

class Thresholds:
    """Max counts and lengths to prevent runaway outputs."""
    # Extractor
    MAX_ENTITIES_PER_EXTRACTION = 200
    MAX_RELATIONS_PER_EXTRACTION = 500
    MAX_CLAIMS_PER_EXTRACTION = 100
    MAX_PROPERTY_VALUE_LENGTH = 50_000
    MAX_ENTITY_PROPERTIES = 50

    # Source gatherer (already in agent_outputs)
    MAX_DOMAINS = 50
    MAX_SOURCES = 200

    # Content fetcher
    MAX_DOMAINS_PER_REQUEST = 10
    MAX_SOURCES_PER_DOMAIN = 50
    MAX_CONTENT_LENGTH = 500_000

    # Linker
    MAX_LINKED_ENTITIES = 500
    MAX_LINKED_RELATIONS = 1000

    # Writer / diff
    MAX_NODES_ADD = 300
    MAX_NODES_UPDATE = 200
    MAX_NODES_DELETE = 100
    MAX_EDGES_ADD = 600
    MAX_EDGES_UPDATE = 400
    MAX_EDGES_DELETE = 200

    # Query
    MAX_QUERY_RESPONSE_LENGTH = 30_000

    # Improvement agent (already in agent_outputs)
    MAX_PROPOSED_FILES = 20
    MAX_FILE_CONTENT_LENGTH = 500_000


# ---------------------------------------------------------------------------
# JSON Schemas (structured I/O) - for documentation and validation
# ---------------------------------------------------------------------------

# Extractor output: entities + relations + claims; claims must reference evidence/source
EXTRACTION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["entities"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "label", "properties"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[A-Z]+:.+"},
                    "label": {"type": "string"},
                    "properties": {"type": "object"}
                }
            }
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from", "to", "type"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "type": {"type": "string"},
                    "properties": {"type": "object"}
                }
            }
        },
        "claims": {"type": "array"}
    }
}

# Provenance: every Claim should link back to evidence/source
# - Claim node: properties.sourceId or properties.evidenceIds
# - Or relation: Evidence -> SUPPORTS -> Claim
PROVENANCE_REQUIRED_FOR_LABELS = frozenset({"Claim", "Evidence", "Position"})

# Content fetcher parsed JSON (LLM output)
CONTENT_FETCHER_PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "domains": {"type": "array", "items": {"type": "string"}},
        "max_sources": {"type": "integer", "minimum": 1, "maximum": 50},
        "min_priority": {"type": "number", "minimum": 0, "maximum": 1}
    }
}

# State update keys that any agent may return (allowlist for merge)
STATE_UPDATE_ALLOWLIST = frozenset({
    "user_input", "chat_id", "intent", "task_queue", "working_notes",
    "proposed_diff", "diff_id", "approval_required", "approval_decision",
    "final_response", "error", "proposed_changes", "improvement_plan",
    "discovered_sources", "scouting_results", "fetched_content"
})
