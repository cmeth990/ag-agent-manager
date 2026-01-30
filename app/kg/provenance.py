"""
Provenance tracking for KG operations.
Ensures: "Can you explain every KG edge with provenance?"
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def create_provenance(
    source_agent: str,
    source_document: Optional[str] = None,
    confidence: float = 1.0,
    reasoning: Optional[str] = None,
    evidence: Optional[str] = None,
    last_verified_at: Optional[str] = None,
    evidence_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create provenance metadata for a KG node or edge.
    Attach this to every node/edge so we can explain "why does this exist?"
    Optional last_verified_at (ISO8601) and evidence_summary support audit trail spec.
    """
    out = {
        "source_agent": str(source_agent),
        "source_document": str(source_document) if source_document else None,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "confidence": float(confidence),
        "reasoning": str(reasoning)[:2000] if reasoning else None,
        "evidence": str(evidence)[:2000] if evidence else None,
    }
    if last_verified_at is not None:
        out["last_verified_at"] = str(last_verified_at)
    if evidence_summary is not None:
        out["evidence_summary"] = str(evidence_summary)[:2000]
    return out


def attach_provenance_to_edge(
    edge: Dict[str, Any],
    source_agent: str,
    source_document: Optional[str] = None,
    confidence: float = 1.0,
    reasoning: Optional[str] = None,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach provenance to an edge dict (in-place and return)."""
    prov = create_provenance(
        source_agent=source_agent,
        source_document=source_document,
        confidence=confidence,
        reasoning=reasoning,
        evidence=evidence,
    )
    props = edge.get("properties") or {}
    props["_provenance"] = prov
    edge["properties"] = props
    return edge


def attach_provenance_to_node(
    node: Dict[str, Any],
    source_agent: str,
    source_document: Optional[str] = None,
    confidence: float = 1.0,
    reasoning: Optional[str] = None,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach provenance to a node dict (in-place and return)."""
    prov = create_provenance(
        source_agent=source_agent,
        source_document=source_document,
        confidence=confidence,
        reasoning=reasoning,
        evidence=evidence,
    )
    props = node.get("properties") or {}
    props["_provenance"] = prov
    node["properties"] = props
    return node


def enrich_diff_with_provenance(
    diff: Dict[str, Any],
    source_agent: str,
    source_document: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add provenance to all nodes and edges in a diff.
    Call this before storing or committing a diff.
    """
    for node in diff.get("nodes", {}).get("add", []) + diff.get("nodes", {}).get("update", []):
        attach_provenance_to_node(
            node,
            source_agent=source_agent,
            source_document=source_document,
            reasoning=reasoning,
        )
    for edge in diff.get("edges", {}).get("add", []) + diff.get("edges", {}).get("update", []):
        attach_provenance_to_edge(
            edge,
            source_agent=source_agent,
            source_document=source_document,
            reasoning=reasoning,
        )
    meta = diff.get("metadata") or {}
    meta["provenance_agent"] = source_agent
    meta["provenance_at"] = datetime.utcnow().isoformat() + "Z"
    diff["metadata"] = meta
    return diff
