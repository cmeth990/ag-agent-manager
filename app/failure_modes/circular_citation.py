"""
Circular citation detection: "self-confirming loops" (agents cite each other).
Detects when agents create circular references that reinforce each other.
"""
import logging
from typing import Dict, Any, List, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class CircularCitationError(Exception):
    """Raised when circular citation is detected."""
    pass


def detect_circular_citations(
    diff: Dict[str, Any],
    existing_edges: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Detect circular citations in a diff.
    
    Pattern: A cites B, B cites C, C cites A (cycle).
    Or: A cites B, B cites A (direct cycle).
    
    Args:
        diff: Diff with nodes/edges to add
        existing_edges: Optional existing edges from KG (for full graph check)
    
    Returns:
        Dict with:
        - has_circular: bool
        - cycles: list of cycle paths (e.g., [["A", "B", "C", "A"]])
        - warnings: list of warning messages
    """
    edges_to_add = diff.get("edges", {}).get("add", [])
    
    # Build citation graph: node -> set of nodes it cites
    citations: Dict[str, Set[str]] = defaultdict(set)
    
    # Add existing edges if provided
    if existing_edges:
        for edge in existing_edges:
            etype = edge.get("type", "")
            if etype in ("SUPPORTS", "REFUTES", "DEFINES", "RELATED_TO"):
                from_id = edge.get("from")
                to_id = edge.get("to")
                if from_id and to_id:
                    citations[from_id].add(to_id)
    
    # Add new edges
    for edge in edges_to_add:
        etype = edge.get("type", "")
        if etype in ("SUPPORTS", "REFUTES", "DEFINES", "RELATED_TO"):
            from_id = edge.get("from")
            to_id = edge.get("to")
            if from_id and to_id:
                citations[from_id].add(to_id)
    
    # Detect cycles using DFS
    cycles = []
    visited = set()
    rec_stack = set()
    
    def dfs(node: str, path: List[str]) -> None:
        if node in rec_stack:
            # Cycle detected
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return
        
        if node in visited:
            return
        
        visited.add(node)
        rec_stack.add(node)
        
        for cited in citations.get(node, set()):
            dfs(cited, path + [node])
        
        rec_stack.remove(node)
    
    # Check all nodes
    all_nodes = set(citations.keys()) | {cited for cites in citations.values() for cited in cites}
    for node in all_nodes:
        if node not in visited:
            dfs(node, [])
    
    has_circular = len(cycles) > 0
    
    warnings = []
    if has_circular:
        for cycle in cycles:
            cycle_str = " -> ".join(cycle[:5])  # Limit display
            warnings.append(f"Circular citation detected: {cycle_str}")
            logger.warning(f"Circular citation: {cycle_str}")
    
    return {
        "has_circular": has_circular,
        "cycles": cycles,
        "warnings": warnings,
    }
