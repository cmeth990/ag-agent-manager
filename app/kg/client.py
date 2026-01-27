"""Knowledge Graph client interface (Neo4j implementation)."""
import os
import logging
from typing import Dict, Any, List, Optional
from app.kg.diff import format_diff_summary
from app.kg.knowledge_base import NODE_TYPES, EDGE_TYPES, get_node_type_from_id
from app.kg.hypernode import (
    detect_orp_pattern, infer_scale_from_content,
    create_fractal_scaling_edge, create_mirror_edge
)

logger = logging.getLogger(__name__)

# Global Neo4j driver instance
_driver = None


def get_neo4j_driver():
    """Get or create Neo4j driver instance."""
    global _driver
    if _driver is not None:
        return _driver
    
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("neo4j package not installed, KG operations will be stubs")
        return None
    
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not password:
        logger.warning("NEO4J_PASSWORD not set, KG operations will be stubs")
        return None
    
    try:
        _driver = GraphDatabase.driver(uri, auth=(username, password))
        # Test connection
        with _driver.session() as session:
            session.run("RETURN 1")
        logger.info(f"Connected to Neo4j at {uri}")
        return _driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return None


async def query_entities(entity_names: List[str]) -> Dict[str, str]:
    """
    Query KG for existing entities by name.
    
    Args:
        entity_names: List of entity names to search for
    
    Returns:
        Dict mapping normalized_name -> entity_id
    """
    driver = get_neo4j_driver()
    if not driver:
        return {}
    
    if not entity_names:
        return {}
    
    # Normalize names for matching
    def normalize_name(name: str) -> str:
        return name.lower().strip().replace(" ", "_").replace("-", "_")
    
    result_map = {}
    
    try:
        with driver.session() as session:
            # Query for entities with matching names or IDs
            # We'll search in the 'name' property and 'id' property
            query = """
            MATCH (n)
            WHERE n.name IN $names 
               OR toLower(n.name) IN $normalized_names
               OR n.id IN $names
            RETURN id(n) as node_id, COALESCE(n.name, n.id) as name, n.id as entity_id
            """
            
            normalized_names = [normalize_name(name) for name in entity_names]
            result = session.run(
                query,
                names=entity_names,
                normalized_names=normalized_names
            )
            
            for record in result:
                node_id = record["node_id"]
                name = record["name"]
                entity_id = record.get("entity_id")
                # Use entity_id if available, otherwise use Neo4j internal ID
                result_id = str(entity_id) if entity_id else str(node_id)
                result_map[normalize_name(name)] = result_id
                # Also map by entity_id if different from name
                if entity_id and normalize_name(str(entity_id)) != normalize_name(name):
                    result_map[normalize_name(str(entity_id))] = result_id
    
    except Exception as e:
        logger.error(f"Error querying entities: {e}", exc_info=True)
    
    return result_map


async def query_kg(query_text: str) -> List[Dict[str, Any]]:
    """
    Query the knowledge graph with natural language or Cypher query.
    
    Args:
        query_text: Natural language query or Cypher query
    
    Returns:
        List of result dictionaries
    """
    driver = get_neo4j_driver()
    if not driver:
        logger.warning("Neo4j not available, returning empty results")
        return []
    
    logger.info(f"Querying KG: {query_text[:100]}...")
    
    # Simple keyword-based query (can be enhanced with LLM to generate Cypher)
    # For now, search for nodes matching the query text
    query_lower = query_text.lower()
    
    try:
        with driver.session() as session:
            # Try to match nodes by name or description
            # Support all KG node types: Concept, Claim, Evidence, Source, Method, Scope, Position
            cypher_query = """
            MATCH (n)
            WHERE toLower(COALESCE(n.name, '')) CONTAINS $query 
               OR toLower(COALESCE(n.description, '')) CONTAINS $query
               OR toLower(COALESCE(n.text, '')) CONTAINS $query
               OR toLower(COALESCE(n.title, '')) CONTAINS $query
            RETURN COALESCE(n.name, n.text, n.title, 'Unknown') as name, 
                   COALESCE(n.description, n.content, '') as description,
                   labels(n) as labels,
                   COALESCE(n.id, toString(id(n))) as node_id,
                   properties(n) as properties
            LIMIT 20
            """
            
            result = session.run(cypher_query, query=query_lower)
            results = []
            
            for record in result:
                result_dict = {
                    "name": record.get("name"),
                    "description": record.get("description"),
                    "labels": record.get("labels", []),
                    "node_id": record.get("node_id"),
                    "properties": dict(record.get("properties", {}))
                }
                results.append(result_dict)
            
            # If no results, try searching relations
            if not results:
                cypher_query = """
                MATCH (a)-[r]->(b)
                WHERE toLower(type(r)) CONTAINS $query
                   OR toLower(COALESCE(a.name, '')) CONTAINS $query
                   OR toLower(COALESCE(b.name, '')) CONTAINS $query
                RETURN a.name as from_name,
                       b.name as to_name,
                       type(r) as type,
                       properties(r) as rel_properties
                LIMIT 20
                """
                
                result = session.run(cypher_query, query=query_lower)
                for record in result:
                    result_dict = {
                        "type": record.get("type"),
                        "from": record.get("from_name"),
                        "to": record.get("to_name"),
                        "properties": dict(record.get("rel_properties", {}))
                    }
                    results.append(result_dict)
            
            logger.info(f"Query returned {len(results)} results")
            return results
    
    except Exception as e:
        logger.error(f"Error querying KG: {e}", exc_info=True)
        return []


async def apply_diff(diff: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a diff to the Neo4j knowledge graph.
    
    Args:
        diff: Diff dict with nodes/edges operations
    
    Returns:
        Result dict with counts, ids, and any errors
    """
    driver = get_neo4j_driver()
    
    if not driver:
        # Fallback to stub behavior
        logger.warning("Neo4j not available, using stub implementation")
        nodes_add = len(diff.get("nodes", {}).get("add", []))
        nodes_update = len(diff.get("nodes", {}).get("update", []))
        nodes_delete = len(diff.get("nodes", {}).get("delete", []))
        edges_add = len(diff.get("edges", {}).get("add", []))
        edges_update = len(diff.get("edges", {}).get("update", []))
        edges_delete = len(diff.get("edges", {}).get("delete", []))
        
        return {
            "success": True,
            "nodes": {
                "added": nodes_add,
                "updated": nodes_update,
                "deleted": nodes_delete
            },
            "edges": {
                "added": edges_add,
                "updated": edges_update,
                "deleted": edges_delete
            },
            "ids": [],
            "errors": []
        }
    
    logger.info(f"Applying KG diff: {format_diff_summary(diff)}")
    
    nodes_add = diff.get("nodes", {}).get("add", [])
    nodes_update = diff.get("nodes", {}).get("update", [])
    nodes_delete = diff.get("nodes", {}).get("delete", [])
    edges_add = diff.get("edges", {}).get("add", [])
    edges_update = diff.get("edges", {}).get("update", [])
    edges_delete = diff.get("edges", {}).get("delete", [])
    
    created_ids = []
    errors = []
    
    try:
        with driver.session() as session:
            # Add nodes
            for node in nodes_add:
                try:
                    node_id = node.get("id")
                    label = node.get("label", "Concept")
                    
                    # Validate label is a known KG node type
                    if label not in NODE_TYPES:
                        # Try to infer from ID
                        inferred_type = get_node_type_from_id(node_id)
                        if inferred_type:
                            label = inferred_type
                        else:
                            label = "Concept"  # Default
                        logger.debug(f"Using label '{label}' for node {node_id}")
                    
                    properties = node.get("properties", {})
                    
                    # Ensure ID is in properties for later matching
                    if "id" not in properties:
                        properties["id"] = node_id
                    
                    # Create node with label and properties
                    query = f"CREATE (n:{label} $properties) RETURN id(n) as node_id, n.id as entity_id"
                    result = session.run(query, properties=properties)
                    record = result.single()
                    if record:
                        neo4j_id = str(record["node_id"])
                        entity_id = record.get("entity_id", node_id)
                        created_ids.append(entity_id)
                        logger.debug(f"Created node {node_id} -> Neo4j ID {neo4j_id}, entity_id {entity_id}")
                except Exception as e:
                    error_msg = f"Error creating node {node.get('id', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Update nodes
            for node in nodes_update:
                try:
                    node_id = node.get("id")
                    label = node.get("label", "Entity")
                    properties = node.get("properties", {})
                    
                    # Try to find node by ID property or Neo4j internal ID
                    query = f"""
                    MATCH (n:{label})
                    WHERE n.id = $node_id OR id(n) = $node_id
                    SET n += $properties
                    RETURN id(n) as node_id
                    """
                    result = session.run(query, node_id=node_id, properties=properties)
                    record = result.single()
                    if not record:
                        logger.warning(f"Node {node_id} not found for update")
                except Exception as e:
                    error_msg = f"Error updating node {node.get('id', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Delete nodes
            for node in nodes_delete:
                try:
                    node_id = node.get("id")
                    label = node.get("label", "Entity")
                    
                    query = f"""
                    MATCH (n:{label})
                    WHERE n.id = $node_id OR id(n) = $node_id
                    DETACH DELETE n
                    """
                    session.run(query, node_id=node_id)
                except Exception as e:
                    error_msg = f"Error deleting node {node.get('id', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Add edges
            for edge in edges_add:
                try:
                    from_id = edge.get("from")
                    to_id = edge.get("to")
                    rel_type = edge.get("type", "RELATED_TO")
                    properties = edge.get("properties", {})
                    
                    # Find nodes by ID property or internal ID
                    query = f"""
                    MATCH (a), (b)
                    WHERE (a.id = $from_id OR id(a) = $from_id)
                      AND (b.id = $to_id OR id(b) = $to_id)
                    CREATE (a)-[r:{rel_type} $properties]->(b)
                    RETURN id(r) as rel_id
                    """
                    result = session.run(
                        query,
                        from_id=from_id,
                        to_id=to_id,
                        properties=properties
                    )
                    record = result.single()
                    if not record:
                        logger.warning(f"Could not create edge from {from_id} to {to_id}")
                except Exception as e:
                    error_msg = f"Error creating edge {edge.get('type', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Update edges (similar to nodes)
            for edge in edges_update:
                try:
                    from_id = edge.get("from")
                    to_id = edge.get("to")
                    rel_type = edge.get("type", "RELATED_TO")
                    properties = edge.get("properties", {})
                    
                    query = f"""
                    MATCH (a)-[r:{rel_type}]->(b)
                    WHERE (a.id = $from_id OR id(a) = $from_id)
                      AND (b.id = $to_id OR id(b) = $to_id)
                    SET r += $properties
                    """
                    session.run(
                        query,
                        from_id=from_id,
                        to_id=to_id,
                        properties=properties
                    )
                except Exception as e:
                    error_msg = f"Error updating edge {edge.get('type', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Delete edges
            for edge in edges_delete:
                try:
                    from_id = edge.get("from")
                    to_id = edge.get("to")
                    rel_type = edge.get("type", "RELATED_TO")
                    
                    query = f"""
                    MATCH (a)-[r:{rel_type}]->(b)
                    WHERE (a.id = $from_id OR id(a) = $from_id)
                      AND (b.id = $to_id OR id(b) = $to_id)
                    DELETE r
                    """
                    session.run(query, from_id=from_id, to_id=to_id)
                except Exception as e:
                    error_msg = f"Error deleting edge {edge.get('type', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
    
    except Exception as e:
        logger.error(f"Error applying diff: {e}", exc_info=True)
        return {
            "success": False,
            "nodes": {"added": 0, "updated": 0, "deleted": 0},
            "edges": {"added": 0, "updated": 0, "deleted": 0},
            "ids": [],
            "errors": [str(e)]
        }
    
    return {
        "success": len(errors) == 0,
        "nodes": {
            "added": len(nodes_add),
            "updated": len(nodes_update),
            "deleted": len(nodes_delete)
        },
        "edges": {
            "added": len(edges_add),
            "updated": len(edges_update),
            "deleted": len(edges_delete)
        },
        "ids": created_ids,
        "errors": errors
    }


async def expand_hypernode(hypernode_id: str, depth: int = 1) -> Dict[str, Any]:
    """
    Expand a hypernode to show its contained subgraph.
    
    Args:
        hypernode_id: ID of the hypernode to expand
        depth: How many levels deep to expand (1 = immediate children only)
    
    Returns:
        Dict with expanded subgraph: {nodes: [], edges: [], hypernode: {}}
    """
    driver = get_neo4j_driver()
    if not driver:
        logger.warning("Neo4j not available, returning empty expansion")
        return {"nodes": [], "edges": [], "hypernode": {}}
    
    try:
        with driver.session() as session:
            # Get hypernode
            query = """
            MATCH (hn:Hypernode)
            WHERE hn.id = $hypernode_id OR id(hn) = $hypernode_id
            RETURN hn, properties(hn) as props
            """
            result = session.run(query, hypernode_id=hypernode_id)
            record = result.single()
            
            if not record:
                logger.warning(f"Hypernode {hypernode_id} not found")
                return {"nodes": [], "edges": [], "hypernode": {}}
            
            hypernode = dict(record["props"])
            
            # Get contained nodes via CONTAINS edges
            query = """
            MATCH (hn:Hypernode)-[r:CONTAINS]->(n)
            WHERE hn.id = $hypernode_id OR id(hn) = $hypernode_id
            RETURN n, labels(n) as labels, properties(n) as props, type(r) as rel_type, properties(r) as rel_props
            LIMIT 100
            """
            result = session.run(query, hypernode_id=hypernode_id)
            
            nodes = []
            edges = []
            node_ids = set()
            
            for record in result:
                node_props = dict(record["props"])
                node_labels = record["labels"]
                node_id = node_props.get("id", str(record["n"].id))
                
                if node_id not in node_ids:
                    nodes.append({
                        "id": node_id,
                        "label": node_labels[0] if node_labels else "Unknown",
                        "properties": node_props
                    })
                    node_ids.add(node_id)
                
                edges.append({
                    "from": hypernode_id,
                    "to": node_id,
                    "type": "CONTAINS",
                    "properties": dict(record.get("rel_props", {}))
                })
            
            # Get edges between contained nodes
            if node_ids:
                query = """
                MATCH (a)-[r]->(b)
                WHERE a.id IN $node_ids AND b.id IN $node_ids
                RETURN a.id as from_id, b.id as to_id, type(r) as rel_type, properties(r) as rel_props
                LIMIT 200
                """
                result = session.run(query, node_ids=list(node_ids))
                
                for record in result:
                    edges.append({
                        "from": record["from_id"],
                        "to": record["to_id"],
                        "type": record["rel_type"],
                        "properties": dict(record.get("rel_props", {}))
                    })
            
            logger.info(f"Expanded hypernode {hypernode_id}: {len(nodes)} nodes, {len(edges)} edges")
            
            return {
                "nodes": nodes,
                "edges": edges,
                "hypernode": hypernode,
                "depth": depth
            }
    
    except Exception as e:
        logger.error(f"Error expanding hypernode: {e}", exc_info=True)
        return {"nodes": [], "edges": [], "hypernode": {}, "error": str(e)}


async def query_fractal_scale(
    node_id: str,
    target_scale: str = "macro",
    max_depth: int = 5
) -> Dict[str, Any]:
    """
    Query fractal scaling relationships (micro → meso → macro).
    
    Args:
        node_id: Starting node ID
        target_scale: Target scale to find (micro, meso, macro)
        max_depth: Maximum traversal depth
    
    Returns:
        Dict with scaled nodes and SCALES_TO edges
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"nodes": [], "edges": [], "scales": []}
    
    try:
        with driver.session() as session:
            # Find nodes at target scale connected via SCALES_TO
            query = """
            MATCH path = (start)-[:SCALES_TO*1..$max_depth]->(target)
            WHERE (start.id = $node_id OR id(start) = $node_id)
              AND target.scale = $target_scale
            RETURN target, labels(target) as labels, properties(target) as props,
                   relationships(path) as rels
            LIMIT 20
            """
            result = session.run(
                query,
                node_id=node_id,
                target_scale=target_scale,
                max_depth=max_depth
            )
            
            nodes = []
            edges = []
            scales = []
            
            for record in result:
                node_props = dict(record["props"])
                node_labels = record["labels"]
                node_id_found = node_props.get("id", str(record["target"].id))
                
                nodes.append({
                    "id": node_id_found,
                    "label": node_labels[0] if node_labels else "Unknown",
                    "properties": node_props
                })
                
                # Extract SCALES_TO edges from path
                rels = record.get("rels", [])
                for rel in rels:
                    if rel.type == "SCALES_TO":
                        edges.append({
                            "from": str(rel.start_node.id),
                            "to": str(rel.end_node.id),
                            "type": "SCALES_TO",
                            "properties": dict(rel)
                        })
                        scales.append({
                            "from_scale": rel.get("from_scale", "unknown"),
                            "to_scale": rel.get("to_scale", "unknown"),
                            "similarity": rel.get("self_similarity_score", 0.0)
                        })
            
            logger.info(f"Found {len(nodes)} nodes at {target_scale} scale from {node_id}")
            
            return {
                "nodes": nodes,
                "edges": edges,
                "scales": scales,
                "target_scale": target_scale
            }
    
    except Exception as e:
        logger.error(f"Error querying fractal scale: {e}", exc_info=True)
        return {"nodes": [], "edges": [], "scales": [], "error": str(e)}


async def query_orp_structure(node_id: str) -> Dict[str, Any]:
    """
    Query ORP structure around a node (objects, relations, processes).
    
    Args:
        node_id: Node ID to query ORP structure for
    
    Returns:
        Dict with ORP components: {objects: [], relations: [], processes: []}
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"objects": [], "relations": [], "processes": []}
    
    try:
        with driver.session() as session:
            # Get objects (Concepts, Claims, Evidence)
            query = """
            MATCH (n)
            WHERE n.id = $node_id OR id(n) = $node_id
            OPTIONAL MATCH (n)-[r1]-(related)
            WHERE labels(related) IN ['Concept', 'Claim', 'Evidence']
            RETURN n, labels(n) as n_labels, properties(n) as n_props,
                   collect(DISTINCT {node: related, labels: labels(related), props: properties(related)}) as objects
            LIMIT 50
            """
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                return {"objects": [], "relations": [], "processes": []}
            
            objects = []
            processes = []
            relations = []
            
            # Add main node as object
            n_props = dict(record["n_props"])
            n_labels = record["n_labels"]
            objects.append({
                "id": n_props.get("id", node_id),
                "label": n_labels[0] if n_labels else "Unknown",
                "properties": n_props
            })
            
            # Add related objects
            for obj_data in record.get("objects", []):
                if obj_data.get("node"):
                    obj_props = dict(obj_data["props"])
                    obj_labels = obj_data["labels"]
                    objects.append({
                        "id": obj_props.get("id", str(obj_data["node"].id)),
                        "label": obj_labels[0] if obj_labels else "Unknown",
                        "properties": obj_props
                    })
            
            # Get processes connected via INPUTS_TO or OUTPUTS_FROM
            query = """
            MATCH (n)
            WHERE n.id = $node_id OR id(n) = $node_id
            OPTIONAL MATCH (n)-[r1:INPUTS_TO|OUTPUTS_FROM]-(p:Process)
            RETURN collect(DISTINCT {node: p, labels: labels(p), props: properties(p), rel: r1}) as processes
            """
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            for proc_data in record.get("processes", []):
                if proc_data.get("node"):
                    proc_props = dict(proc_data["props"])
                    proc_labels = proc_data["labels"]
                    processes.append({
                        "id": proc_props.get("id", str(proc_data["node"].id)),
                        "label": "Process",
                        "properties": proc_props
                    })
                    # Add relation
                    rel = proc_data.get("rel")
                    if rel:
                        relations.append({
                            "from": node_id if rel.type == "INPUTS_TO" else str(rel.start_node.id),
                            "to": str(rel.end_node.id) if rel.type == "INPUTS_TO" else node_id,
                            "type": rel.type,
                            "properties": dict(rel)
                        })
            
            logger.info(f"Found ORP structure: {len(objects)} objects, {len(processes)} processes, {len(relations)} relations")
            
            return {
                "objects": objects,
                "relations": relations,
                "processes": processes
            }
    
    except Exception as e:
        logger.error(f"Error querying ORP structure: {e}", exc_info=True)
        return {"objects": [], "relations": [], "processes": [], "error": str(e)}
