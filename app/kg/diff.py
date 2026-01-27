"""Knowledge Graph diff format and utilities."""
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime


def create_diff_id() -> str:
    """Generate a unique diff ID."""
    return str(uuid.uuid4())


def format_diff_summary(diff: Dict[str, Any]) -> str:
    """
    Format a diff into a human-readable summary.
    
    Args:
        diff: Diff dict with nodes/edges operations
    
    Returns:
        Formatted summary string
    """
    nodes_add = len(diff.get("nodes", {}).get("add", []))
    nodes_update = len(diff.get("nodes", {}).get("update", []))
    nodes_delete = len(diff.get("nodes", {}).get("delete", []))
    edges_add = len(diff.get("edges", {}).get("add", []))
    edges_update = len(diff.get("edges", {}).get("update", []))
    edges_delete = len(diff.get("edges", {}).get("delete", []))
    
    parts = []
    if nodes_add > 0:
        parts.append(f"+{nodes_add} nodes")
    if nodes_update > 0:
        parts.append(f"~{nodes_update} nodes")
    if nodes_delete > 0:
        parts.append(f"-{nodes_delete} nodes")
    if edges_add > 0:
        parts.append(f"+{edges_add} edges")
    if edges_update > 0:
        parts.append(f"~{edges_update} edges")
    if edges_delete > 0:
        parts.append(f"-{edges_delete} edges")
    
    if not parts:
        return "No changes"
    
    return ", ".join(parts)


def create_empty_diff() -> Dict[str, Any]:
    """Create an empty diff structure."""
    return {
        "nodes": {
            "add": [],
            "update": [],
            "delete": []
        },
        "edges": {
            "add": [],
            "update": [],
            "delete": []
        },
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "source": None,
            "reason": None
        }
    }
