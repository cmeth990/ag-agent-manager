"""
Overarching mission for the superintendent agent.

The superintendent constantly monitors, improves, and updates the agents,
and comes to the user for key decisions at crucial intersections.
"""

OVERARCHING_MISSION = """
Build and maintain a decision-grade knowledge graph that:
1. Uses free secondary sources (APIs, indexes) to identify primary sources (DOI, arXiv, etc.) and secure claims.
2. Expands the graph autonomously across domains (discovery → primary IDs → optional fetch/ingest).
3. Monitors agents, queue, cost, and KG health; improves agents when gaps or failures are detected.
4. Surfaces crucial decisions to the human: approve/reject KG writes, approve/reject code changes, resolve contradictions, prioritize domains, handle budget caps.
"""

# Decision points where the superintendent must stop and get human input
CRUCIAL_DECISION_TYPES = {
    "kg_write": "Commit or reject proposed KG changes (nodes/edges).",
    "code_change": "Apply or reject proposed code/agent improvements.",
    "contradiction_resolution": "How to resolve conflicting claims (flag, prefer new, prefer existing).",
    "domain_priority": "Which domains to expand next when multiple candidates exist.",
    "budget_cap": "Budget limit approached; pause expansion or continue with reduced scope.",
    "stuck_tasks": "Tasks stuck in queue; retry, skip, or triage.",
}


def get_mission_summary() -> str:
    """Short summary for prompts and help text."""
    return (
        "Mission: Build a decision-grade KG using secondary→primary methodology; "
        "expand autonomously; monitor and improve agents; come to the user for key decisions "
        "(KG commit, code change, contradiction, priority, budget, stuck tasks)."
    )


def get_crucial_decision_label(decision_type: str) -> str:
    """Human-readable label for a crucial decision type."""
    return CRUCIAL_DECISION_TYPES.get(decision_type, "Key decision")
