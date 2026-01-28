"""
Idempotent writes to KG: upsert patterns.
Enables: "Idempotent writes to KG"
- Check before create (MERGE pattern)
- Upsert on conflict
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def build_upsert_node_query(
    node_id: str,
    label: str,
    properties: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """
    Build a Cypher MERGE query for idempotent node creation.
    MERGE creates if not exists, otherwise matches existing.
    
    Returns:
        (query, params) tuple
    """
    # MERGE on ID property (if present) or node ID
    query = f"""
    MERGE (n:{label} {{id: $node_id}})
    ON CREATE SET n = $properties, n.created_at = timestamp()
    ON MATCH SET n += $properties, n.updated_at = timestamp()
    RETURN id(n) as node_id, n.id as entity_id
    """
    params = {
        "node_id": node_id,
        "properties": properties,
    }
    return query, params


def build_upsert_edge_query(
    from_id: str,
    to_id: str,
    rel_type: str,
    properties: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """
    Build a Cypher MERGE query for idempotent edge creation.
    MERGE creates if not exists, otherwise matches existing.
    
    Returns:
        (query, params) tuple
    """
    query = f"""
    MATCH (a), (b)
    WHERE (a.id = $from_id OR id(a) = $from_id)
      AND (b.id = $to_id OR id(b) = $to_id)
    MERGE (a)-[r:{rel_type}]->(b)
    ON CREATE SET r = $properties, r.created_at = timestamp()
    ON MATCH SET r += $properties, r.updated_at = timestamp()
    RETURN id(r) as rel_id
    """
    params = {
        "from_id": from_id,
        "to_id": to_id,
        "properties": properties,
    }
    return query, params
