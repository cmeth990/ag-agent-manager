"""
Cross-source corroboration: require 2+ independent sources for key facts.
Claims/facts without sufficient corroboration can be flagged or rejected.
"""
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class CorroborationError(Exception):
    """Raised when a claim/fact does not have sufficient corroboration."""
    pass


def _get_source_ids_from_provenance(edge_or_node: Dict[str, Any]) -> Set[str]:
    """Extract source identifiers from _provenance or source_document."""
    source_ids: Set[str] = set()
    props = edge_or_node.get("properties") or {}
    prov = props.get("_provenance") or {}
    doc = prov.get("source_document") or props.get("source_document")
    if doc:
        source_ids.add(str(doc))
    # Evidence pointer
    evidence = prov.get("evidence") or props.get("evidence")
    if evidence:
        source_ids.add(str(evidence)[:200])
    return source_ids


def _get_source_ids_from_diff_node(node: Dict[str, Any]) -> Set[str]:
    """Extract source IDs from a node in a diff (before apply)."""
    props = node.get("properties") or {}
    prov = props.get("_provenance") or {}
    doc = prov.get("source_document")
    if doc:
        return {str(doc)}
    return set()


def require_corroboration(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    min_sources: int = 2,
    require_for_claims_only: bool = True,
) -> Dict[str, Any]:
    """
    Check that key facts (Claim nodes or high-impact edges) have 2+ independent sources.
    
    Args:
        nodes: List of node dicts (e.g. from diff nodes.add)
        edges: List of edge dicts
        min_sources: Minimum number of distinct sources required
        require_for_claims_only: If True, only enforce for Claim nodes and DEFINES/SUPPORTS edges
    
    Returns:
        Dict with:
        - allowed: list of node/edge indices or ids that pass
        - flagged: list of items that don't have enough sources
        - errors: list of CorroborationError messages
    """
    allowed = []
    flagged = []
    errors = []
    
    # Build set of node ids that have sufficient provenance
    node_sources: Dict[str, Set[str]] = {}
    for i, node in enumerate(nodes):
        nid = node.get("id", f"node_{i}")
        srcs = _get_source_ids_from_diff_node(node)
        node_sources[nid] = srcs
        label = node.get("label", "Concept")
        
        if require_for_claims_only and label != "Claim":
            allowed.append(("node", i, nid))
            continue
        
        if len(srcs) >= min_sources:
            allowed.append(("node", i, nid))
        else:
            flagged.append(("node", i, nid, list(srcs)))
            if label == "Claim":
                errors.append(
                    CorroborationError(
                        f"Claim node {nid} has {len(srcs)} source(s); required {min_sources}"
                    )
                )
    
    # Check edges (DEFINES, SUPPORTS are key for claims)
    key_edge_types = {"DEFINES", "SUPPORTS", "REFUTES"}
    for i, edge in enumerate(edges):
        etype = edge.get("type", "RELATED_TO")
        if require_for_claims_only and etype not in key_edge_types:
            allowed.append(("edge", i, None))
            continue
        
        # Edge provenance: from edge properties
        props = edge.get("properties") or {}
        prov = props.get("_provenance") or {}
        doc = prov.get("source_document")
        srcs = {str(doc)} if doc else set()
        
        if len(srcs) >= min_sources:
            allowed.append(("edge", i, None))
        else:
            flagged.append(("edge", i, None, list(srcs)))
            errors.append(
                CorroborationError(
                    f"Edge {edge.get('from')} -[{etype}]-> {edge.get('to')} has {len(srcs)} source(s); required {min_sources}"
                )
            )
    
    return {"allowed": allowed, "flagged": flagged, "errors": errors}


def filter_diff_by_corroboration(
    diff: Dict[str, Any],
    min_sources: int = 2,
    require_for_claims_only: bool = True,
) -> Dict[str, Any]:
    """
    Filter a diff to remove nodes/edges that don't meet corroboration requirement.
    Returns new diff with only allowed items; flagged items are logged and dropped.
    """
    nodes_add = diff.get("nodes", {}).get("add", [])
    edges_add = diff.get("edges", {}).get("add", [])
    
    result = require_corroboration(
        nodes_add, edges_add,
        min_sources=min_sources,
        require_for_claims_only=require_for_claims_only,
    )
    
    if result["flagged"]:
        for item in result["flagged"]:
            kind, idx, id_or_none, srcs = item
            logger.warning(
                f"Corroboration: {kind} {idx} (sources: {len(srcs)}) dropped - need {min_sources}+ sources"
            )
    
    # Build filtered diff (for now we allow all; flagging is logged - could be strict later)
    # Option: remove flagged nodes/edges from diff
    filtered_nodes = []
    filtered_edges = []
    allowed_nodes = {idx for (k, idx, _) in result["allowed"] if k == "node"}
    allowed_edges = {idx for (k, idx, _) in result["allowed"] if k == "edge"}
    
    for i, n in enumerate(nodes_add):
        if i in allowed_nodes:
            filtered_nodes.append(n)
        else:
            logger.info(f"Dropping node {n.get('id')} (insufficient corroboration)")
    
    for i, e in enumerate(edges_add):
        if i in allowed_edges:
            filtered_edges.append(e)
        else:
            logger.info(f"Dropping edge {e.get('from')} -> {e.get('to')} (insufficient corroboration)")
    
    from copy import deepcopy
    out = deepcopy(diff)
    out["nodes"]["add"] = filtered_nodes
    out["edges"]["add"] = filtered_edges
    return out
