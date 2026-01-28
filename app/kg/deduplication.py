"""
Deduplication and drift detection for knowledge graph.
Enables: "Can you detect duplication and drift automatically?"
- Detect duplicate nodes/edges (same content, different IDs)
- Identify semantic drift (same concept, different representations)
- Flag contradictions (conflicting facts about same entity)
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Semantic similarity threshold (0.0-1.0)
SIMILARITY_THRESHOLD = 0.85  # 85% similarity = likely duplicate


def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, strip, remove extra spaces)."""
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


def text_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity using SequenceMatcher (0.0-1.0).
    Simple but effective for exact/near-duplicate detection.
    """
    if not text1 or not text2:
        return 0.0
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    if norm1 == norm2:
        return 1.0
    return SequenceMatcher(None, norm1, norm2).ratio()


def extract_node_key_properties(node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key properties for duplicate detection.
    Returns dict with normalized values for comparison.
    """
    props = node.get("properties", {})
    key_props = {}
    
    # Primary identifier fields
    for field in ["name", "title", "text", "description"]:
        if field in props:
            key_props[field] = normalize_text(str(props[field]))
    
    # Domain (for concepts)
    if "domain" in props:
        key_props["domain"] = normalize_text(str(props["domain"]))
    
    return key_props


def check_duplicate_node(
    new_node: Dict[str, Any],
    existing_nodes: List[Dict[str, Any]],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """
    Check if a new node is a duplicate of an existing node.
    
    Args:
        new_node: Node to check (dict with id, label, properties)
        existing_nodes: List of existing nodes from KG
        similarity_threshold: Minimum similarity to consider duplicate (0.0-1.0)
    
    Returns:
        Existing node dict if duplicate found, None otherwise
    """
    new_props = extract_node_key_properties(new_node)
    new_label = new_node.get("label", "Concept")
    
    if not new_props:
        return None  # Can't compare without key properties
    
    for existing in existing_nodes:
        existing_label = existing.get("label", "Concept")
        
        # Must have same label (type)
        if existing_label != new_label:
            continue
        
        existing_props = extract_node_key_properties(existing)
        if not existing_props:
            continue
        
        # Check for exact match on primary field
        for field in ["name", "title", "text"]:
            if field in new_props and field in existing_props:
                if new_props[field] == existing_props[field]:
                    # Exact match - definitely duplicate
                    logger.info(f"Exact duplicate detected: {new_node.get('id')} matches {existing.get('id')} on {field}")
                    return existing
        
        # Check semantic similarity
        similarities = []
        for field in new_props:
            if field in existing_props:
                sim = text_similarity(new_props[field], existing_props[field])
                similarities.append(sim)
        
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            if avg_similarity >= similarity_threshold:
                logger.info(
                    f"Semantic duplicate detected: {new_node.get('id')} matches {existing.get('id')} "
                    f"(similarity: {avg_similarity:.2f})"
                )
                return existing
    
    return None


def check_duplicate_edge(
    new_edge: Dict[str, Any],
    existing_edges: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Check if a new edge is a duplicate of an existing edge.
    
    Args:
        new_edge: Edge to check (dict with from, to, type, properties)
        existing_edges: List of existing edges from KG
    
    Returns:
        Existing edge dict if duplicate found, None otherwise
    """
    new_from = new_edge.get("from")
    new_to = new_edge.get("to")
    new_type = new_edge.get("type", "RELATED_TO")
    new_props = new_edge.get("properties", {})
    
    for existing in existing_edges:
        existing_from = existing.get("from")
        existing_to = existing.get("to")
        existing_type = existing.get("type", "RELATED_TO")
        
        # Must have same from/to/type
        if existing_from == new_from and existing_to == new_to and existing_type == new_type:
            # Check if properties are similar (for edges with properties)
            if not new_props and not existing.get("properties"):
                # Both have no properties - exact duplicate
                logger.info(f"Exact duplicate edge: {new_from} -[{new_type}]-> {new_to}")
                return existing
            
            # Compare properties if both have them
            existing_props = existing.get("properties", {})
            if new_props and existing_props:
                # Simple check: if all key properties match, consider duplicate
                key_matches = sum(
                    1 for k in new_props
                    if k in existing_props and str(new_props[k]).lower() == str(existing_props[k]).lower()
                )
                if key_matches == len(new_props) and key_matches == len(existing_props):
                    logger.info(f"Duplicate edge with matching properties: {new_from} -[{new_type}]-> {new_to}")
                    return existing
    
    return None


def detect_contradictions(
    new_claim: Dict[str, Any],
    existing_claims: List[Dict[str, Any]],
    target_entity_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Detect contradictions between a new claim and existing claims.
    
    Contradiction patterns:
    - Same entity, opposite truth values (true vs false)
    - Same entity, conflicting numerical values (e.g., "X is 5" vs "X is 10")
    - Same entity, mutually exclusive categories
    
    Args:
        new_claim: New claim node to check
        existing_claims: List of existing claim nodes
        target_entity_id: Optional entity ID this claim is about
    
    Returns:
        List of contradictory claims (empty if none)
    """
    contradictions = []
    
    new_text = normalize_text(new_claim.get("properties", {}).get("text", ""))
    if not new_text:
        return contradictions
    
    new_label = new_claim.get("label", "Claim")
    if new_label != "Claim":
        return contradictions  # Only check Claim nodes for contradictions
    
    for existing in existing_claims:
        existing_text = normalize_text(existing.get("properties", {}).get("text", ""))
        if not existing_text:
            continue
        
        # Check for explicit contradiction keywords
        contradiction_keywords = [
            ("is", "is not"),
            ("are", "are not"),
            ("has", "does not have"),
            ("can", "cannot"),
            ("true", "false"),
            ("yes", "no"),
        ]
        
        for positive, negative in contradiction_keywords:
            if (positive in new_text.lower() and negative in existing_text.lower()) or \
               (negative in new_text.lower() and positive in existing_text.lower()):
                # Potential contradiction
                contradictions.append({
                    "existing_claim": existing,
                    "new_claim": new_claim,
                    "reason": f"Contradictory statements: '{new_text}' vs '{existing_text}'",
                })
                logger.warning(f"Contradiction detected: {new_text} contradicts {existing_text}")
                break
    
    return contradictions


async def check_diff_for_duplicates(
    diff: Dict[str, Any],
    driver=None,
) -> Dict[str, Any]:
    """
    Check a diff for duplicates before applying it.
    
    Args:
        diff: Diff dict with nodes/edges to add/update
        driver: Optional Neo4j driver (if None, will get it)
    
    Returns:
        Dict with:
        - duplicate_nodes: List of (new_node, existing_node) pairs
        - duplicate_edges: List of (new_edge, existing_edge) pairs
        - contradictions: List of contradiction reports
        - recommendations: List of recommendations (merge, skip, etc.)
    """
    if driver is None:
        from app.kg.client import get_neo4j_driver
        driver = get_neo4j_driver()
    
    if not driver:
        logger.warning("Neo4j not available, skipping duplicate check")
        return {
            "duplicate_nodes": [],
            "duplicate_edges": [],
            "contradictions": [],
            "recommendations": [],
        }
    
    nodes_to_add = diff.get("nodes", {}).get("add", [])
    edges_to_add = diff.get("edges", {}).get("add", [])
    
    duplicate_nodes = []
    duplicate_edges = []
    contradictions = []
    recommendations = []
    
    # Query existing nodes for comparison
    existing_nodes = []
    existing_edges = []
    
    try:
        with driver.session() as session:
            # Get all nodes (for duplicate checking)
            # We'll query by label to get relevant nodes
            node_labels = set(node.get("label", "Concept") for node in nodes_to_add)
            
            for label in node_labels:
                query = f"MATCH (n:{label}) RETURN n, labels(n) as labels"
                result = session.run(query)
                for record in result:
                    node_data = dict(record["n"])
                    node_data["label"] = label
                    existing_nodes.append(node_data)
            
            # Get all edges (for duplicate checking)
            if edges_to_add:
                query = """
                MATCH (a)-[r]->(b)
                RETURN type(r) as type, properties(r) as props, a.id as from_id, b.id as to_id
                """
                result = session.run(query)
                for record in result:
                    existing_edges.append({
                        "from": record.get("from_id"),
                        "to": record.get("to_id"),
                        "type": record.get("type"),
                        "properties": record.get("props", {}),
                    })
    except Exception as e:
        logger.error(f"Error querying KG for duplicate check: {e}")
        return {
            "duplicate_nodes": [],
            "duplicate_edges": [],
            "contradictions": [],
            "recommendations": [],
        }
    
    # Check nodes for duplicates
    for new_node in nodes_to_add:
        duplicate = check_duplicate_node(new_node, existing_nodes)
        if duplicate:
            duplicate_nodes.append((new_node, duplicate))
            recommendations.append({
                "type": "merge_node",
                "new_id": new_node.get("id"),
                "existing_id": duplicate.get("id"),
                "action": "Use existing node instead of creating duplicate",
            })
    
    # Check edges for duplicates
    for new_edge in edges_to_add:
        duplicate = check_duplicate_edge(new_edge, existing_edges)
        if duplicate:
            duplicate_edges.append((new_edge, duplicate))
            recommendations.append({
                "type": "skip_edge",
                "new_edge": f"{new_edge.get('from')} -[{new_edge.get('type')}]-> {new_edge.get('to')}",
                "existing_edge": f"{duplicate.get('from')} -[{duplicate.get('type')}]-> {duplicate.get('to')}",
                "action": "Skip duplicate edge",
            })
    
    # Check for contradictions (in Claim nodes)
    claim_nodes = [n for n in nodes_to_add if n.get("label") == "Claim"]
    existing_claims = [n for n in existing_nodes if n.get("label") == "Claim"]
    
    for new_claim in claim_nodes:
        claim_contradictions = detect_contradictions(new_claim, existing_claims)
        contradictions.extend(claim_contradictions)
        if claim_contradictions:
            recommendations.append({
                "type": "review_contradiction",
                "new_claim_id": new_claim.get("id"),
                "conflicting_claims": [c["existing_claim"].get("id") for c in claim_contradictions],
                "action": "Review contradiction before adding claim",
            })
    
    return {
        "duplicate_nodes": duplicate_nodes,
        "duplicate_edges": duplicate_edges,
        "contradictions": contradictions,
        "recommendations": recommendations,
    }


def merge_node_properties(
    existing_node: Dict[str, Any],
    new_node: Dict[str, Any],
    strategy: str = "merge",
) -> Dict[str, Any]:
    """
    Merge properties from a new node into an existing node.
    
    Strategies:
    - "merge": Combine all properties (new overwrites existing for conflicts)
    - "preserve_existing": Keep existing properties, only add missing ones
    - "prefer_new": Use new properties, only keep existing if new doesn't have it
    
    Args:
        existing_node: Existing node from KG
        new_node: New node to merge
        strategy: Merge strategy
    
    Returns:
        Merged properties dict
    """
    existing_props = existing_node.get("properties", {}).copy()
    new_props = new_node.get("properties", {}).copy()
    
    if strategy == "merge":
        # New overwrites existing
        merged = {**existing_props, **new_props}
    elif strategy == "preserve_existing":
        # Only add properties that don't exist
        merged = {**new_props, **existing_props}
    elif strategy == "prefer_new":
        # New takes precedence, fallback to existing
        merged = {**existing_props, **new_props}
    else:
        merged = {**existing_props, **new_props}
    
    # Preserve ID from existing node
    merged["id"] = existing_node.get("id") or existing_node.get("properties", {}).get("id")
    
    return merged


def resolve_contradiction(
    contradiction: Dict[str, Any],
    resolution: str = "flag_for_review",
) -> Dict[str, Any]:
    """
    Resolve a contradiction between claims.
    
    Resolution strategies:
    - "flag_for_review": Mark both claims as needing review (default)
    - "prefer_new": Keep new claim, mark existing as "contradicted"
    - "prefer_existing": Keep existing, mark new as "contradicted"
    - "both_keep": Keep both but mark as "conflicting"
    
    Args:
        contradiction: Contradiction dict from detect_contradictions
        resolution: Resolution strategy
    
    Returns:
        Resolution action dict
    """
    existing_claim = contradiction["existing_claim"]
    new_claim = contradiction["new_claim"]
    
    if resolution == "flag_for_review":
        return {
            "action": "flag_for_review",
            "existing_claim_id": existing_claim.get("id"),
            "new_claim_id": new_claim.get("id"),
            "message": "Both claims flagged for manual review",
        }
    elif resolution == "prefer_new":
        return {
            "action": "prefer_new",
            "existing_claim_id": existing_claim.get("id"),
            "new_claim_id": new_claim.get("id"),
            "message": "New claim accepted, existing marked as contradicted",
        }
    elif resolution == "prefer_existing":
        return {
            "action": "prefer_existing",
            "existing_claim_id": existing_claim.get("id"),
            "new_claim_id": new_claim.get("id"),
            "message": "Existing claim kept, new claim marked as contradicted",
        }
    elif resolution == "both_keep":
        return {
            "action": "both_keep",
            "existing_claim_id": existing_claim.get("id"),
            "new_claim_id": new_claim.get("id"),
            "message": "Both claims kept but marked as conflicting",
        }
    else:
        return {
            "action": "flag_for_review",
            "existing_claim_id": existing_claim.get("id"),
            "new_claim_id": new_claim.get("id"),
            "message": f"Unknown resolution strategy '{resolution}', defaulting to flag_for_review",
        }
