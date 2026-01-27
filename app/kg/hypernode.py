"""
Hypernode operations for fractal knowledge graph structure.
Enables nested subgraphs, ORP modeling, and fractal navigation.
"""
import logging
from typing import Dict, Any, List, Optional
from app.kg.knowledge_base import generate_id, NODE_TYPES, ORP_SCALES

logger = logging.getLogger(__name__)


def create_hypernode(
    name: str,
    scale: str = "meso",
    subgraph_nodes: Optional[List[str]] = None,
    subgraph_edges: Optional[List[str]] = None,
    orp_structure: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a hypernode that encapsulates a subgraph.
    
    Args:
        name: Name of the hypernode
        scale: ORP scale (micro, meso, macro)
        subgraph_nodes: List of node IDs contained in this hypernode
        subgraph_edges: List of edge IDs contained in this hypernode
        orp_structure: ORP metadata {objects: [], relations: [], processes: []}
        **kwargs: Additional properties
    
    Returns:
        Hypernode dict ready for KG insertion
    """
    hypernode_id = generate_id("Hypernode")
    
    if scale not in ORP_SCALES:
        logger.warning(f"Unknown scale '{scale}', defaulting to 'meso'")
        scale = "meso"
    
    hypernode = {
        "id": hypernode_id,
        "label": "Hypernode",
        "properties": {
            "id": hypernode_id,
            "name": name,
            "scale": scale,
            "subgraph_nodes": subgraph_nodes or [],
            "subgraph_edges": subgraph_edges or [],
            "compression_level": kwargs.get("compression_level", 0.5),
            "fractal_depth": kwargs.get("fractal_depth", 1),
            "orp_structure": orp_structure or {
                "objects": [],
                "relations": [],
                "processes": []
            },
            "aggregated_properties": kwargs.get("aggregated_properties", {}),
            **{k: v for k, v in kwargs.items() if k not in ["compression_level", "fractal_depth", "aggregated_properties"]}
        }
    }
    
    logger.info(f"Created hypernode {hypernode_id} ({name}) at {scale} scale")
    return hypernode


def create_process_node(
    name: str,
    process_type: str,
    inputs: Optional[List[str]] = None,
    outputs: Optional[List[str]] = None,
    scale: str = "micro",
    **kwargs
) -> Dict[str, Any]:
    """
    Create a Process node for ORP modeling.
    
    Args:
        name: Name of the process
        process_type: Type of process (e.g., "transformation", "evaluation", "propagation")
        inputs: List of input node IDs
        outputs: List of output node IDs
        scale: ORP scale (micro, meso, macro)
        **kwargs: Additional properties
    
    Returns:
        Process node dict ready for KG insertion
    """
    process_id = generate_id("Process")
    
    if scale not in ORP_SCALES:
        logger.warning(f"Unknown scale '{scale}', defaulting to 'micro'")
        scale = "micro"
    
    process = {
        "id": process_id,
        "label": "Process",
        "properties": {
            "id": process_id,
            "name": name,
            "processType": process_type,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "scale": scale,
            "transformation": kwargs.get("transformation", ""),
            **{k: v for k, v in kwargs.items() if k not in ["transformation"]}
        }
    }
    
    logger.info(f"Created process {process_id} ({name}) at {scale} scale")
    return process


def create_orp_structure(
    objects: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    processes: List[Dict[str, Any]],
    scale: str = "micro"
) -> Dict[str, Any]:
    """
    Create a complete ORP structure with objects, relations, and processes.
    
    Args:
        objects: List of object nodes (Concepts, Claims, Evidence)
        relations: List of relation edges
        processes: List of Process nodes
        scale: ORP scale (micro, meso, macro)
    
    Returns:
        Dict with nodes, edges, and ORP metadata
    """
    all_nodes = objects + processes
    all_edges = relations
    
    # Create hypernode to encapsulate this ORP structure
    hypernode = create_hypernode(
        name=f"ORP_{scale}_{len(objects)}objects",
        scale=scale,
        subgraph_nodes=[obj["id"] for obj in all_nodes],
        subgraph_edges=[rel.get("id", f"edge_{i}") for i, rel in enumerate(all_edges)],
        orp_structure={
            "objects": [obj["id"] for obj in objects],
            "relations": [rel.get("id", f"rel_{i}") for i, rel in enumerate(relations)],
            "processes": [proc["id"] for proc in processes]
        }
    )
    
    # Create CONTAINS edges from hypernode to all nodes
    contains_edges = []
    for node in all_nodes:
        contains_edges.append({
            "from": hypernode["id"],
            "to": node["id"],
            "type": "CONTAINS",
            "properties": {
                "containment_type": "orp_structure",
                "compression_level": 0.5
            }
        })
    
    # Create INPUTS_TO and OUTPUTS_FROM edges for processes
    process_edges = []
    for process in processes:
        process_id = process["id"]
        # Inputs
        for input_id in process.get("properties", {}).get("inputs", []):
            process_edges.append({
                "from": input_id,
                "to": process_id,
                "type": "INPUTS_TO",
                "properties": {
                    "input_type": "object",
                    "scale": scale,
                    "weight": 1.0
                }
            })
        # Outputs
        for output_id in process.get("properties", {}).get("outputs", []):
            process_edges.append({
                "from": process_id,
                "to": output_id,
                "type": "OUTPUTS_FROM",
                "properties": {
                    "output_type": "object",
                    "scale": scale,
                    "strength": 1.0
                }
            })
    
    return {
        "nodes": all_nodes + [hypernode],
        "edges": all_edges + contains_edges + process_edges,
        "hypernode_id": hypernode["id"],
        "orp_metadata": {
            "scale": scale,
            "object_count": len(objects),
            "relation_count": len(relations),
            "process_count": len(processes)
        }
    }


def detect_orp_pattern(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect ORP patterns in a subgraph.
    
    Args:
        nodes: List of nodes in subgraph
        edges: List of edges in subgraph
    
    Returns:
        Dict with detected ORP structure: {objects: [], relations: [], processes: []}
    """
    objects = []
    relations = []
    processes = []
    
    for node in nodes:
        node_type = node.get("label", "")
        if node_type in ["Concept", "Claim", "Evidence", "Source"]:
            objects.append(node)
        elif node_type == "Process":
            processes.append(node)
    
    for edge in edges:
        edge_type = edge.get("type", "")
        # Standard relations
        if edge_type in ["DEFINES", "SUPPORTS", "PREREQ", "PartOf", "IsA", "RELATED_TO"]:
            relations.append(edge)
        # ORP-specific relations
        elif edge_type in ["ENABLES", "INPUTS_TO", "OUTPUTS_FROM"]:
            relations.append(edge)
    
    return {
        "objects": objects,
        "relations": relations,
        "processes": processes,
        "detected": len(objects) > 0 or len(processes) > 0
    }


def infer_scale_from_content(content: str, node_count: int = 0) -> str:
    """
    Infer ORP scale from content characteristics.
    
    Args:
        content: Text content or description
        node_count: Number of nodes in the structure
    
    Returns:
        Inferred scale: "micro", "meso", or "macro"
    """
    content_lower = content.lower()
    
    # Macro indicators
    macro_keywords = ["domain", "hierarchy", "system", "architecture", "framework", "meta", "overall", "global"]
    if any(kw in content_lower for kw in macro_keywords) or node_count > 50:
        return "macro"
    
    # Meso indicators
    meso_keywords = ["cluster", "group", "subgraph", "module", "component", "gate", "circuit"]
    if any(kw in content_lower for kw in meso_keywords) or (10 <= node_count <= 50):
        return "meso"
    
    # Default to micro
    return "micro"


def create_fractal_scaling_edge(
    from_node_id: str,
    to_node_id: str,
    from_scale: str,
    to_scale: str,
    similarity_score: float = 0.8
) -> Dict[str, Any]:
    """
    Create a SCALES_TO edge representing fractal scaling.
    
    Args:
        from_node_id: Source node ID
        to_node_id: Target node ID
        from_scale: Scale of source (micro, meso, macro)
        to_scale: Scale of target (micro, meso, macro)
        similarity_score: Self-similarity score (0-1)
    
    Returns:
        SCALES_TO edge dict
    """
    return {
        "from": from_node_id,
        "to": to_node_id,
        "type": "SCALES_TO",
        "properties": {
            "from_scale": from_scale,
            "to_scale": to_scale,
            "self_similarity_score": similarity_score
        }
    }


def create_mirror_edge(
    node1_id: str,
    node2_id: str,
    mirror_scale: str,
    similarity_score: float = 0.9,
    pattern_type: str = "orp_structure"
) -> Dict[str, Any]:
    """
    Create a MIRRORS edge representing self-similar patterns.
    
    Args:
        node1_id: First node ID
        node2_id: Second node ID
        mirror_scale: Scale at which mirroring occurs
        similarity_score: Similarity score (0-1)
        pattern_type: Type of pattern being mirrored
    
    Returns:
        MIRRORS edge dict
    """
    return {
        "from": node1_id,
        "to": node2_id,
        "type": "MIRRORS",
        "properties": {
            "mirror_scale": mirror_scale,
            "similarity_score": similarity_score,
            "pattern_type": pattern_type
        }
    }
