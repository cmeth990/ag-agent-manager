"""
Category Taxonomy and Hypernode Generation
Creates Upper Ontology and Category hypernodes with ORP structure.
"""
import logging
from typing import Dict, Any, List
from app.kg.hypernode import create_hypernode, create_process_node
from app.kg.knowledge_base import generate_id

logger = logging.getLogger(__name__)

# Upper Ontology Categories (Level 1 - above domains)
UPPER_ONTOLOGY = {
    "entities": {
        "label": "Entities",
        "description": "Concrete/Abstract objects - domains focusing on 'things'",
        "orp_role": "Objects",
        "categories": ["natural_sciences", "social_sciences", "health_medicine"]
    },
    "relations": {
        "label": "Relations",
        "description": "Connections like causal, logical - domains emphasizing interactions",
        "orp_role": "Relations",
        "categories": ["mathematics", "engineering", "philosophy_religion"]
    },
    "events_processes": {
        "label": "Events/Processes",
        "description": "Dynamic changes - domains modeling sequences and temporal phenomena",
        "orp_role": "Processes",
        "categories": ["history", "business_economics", "interdisciplinary", 
                      "languages_literature", "arts", "vocational"]
    }
}

# Primary Categories (Level 2 - group domains)
CATEGORIES = {
    "mathematics": {
        "label": "Mathematics & Computational Sciences",
        "upper_ontology": "relations",
        "orp_role": "Relations",
        "domain_count": 44
    },
    "natural_sciences": {
        "label": "Natural Sciences",
        "upper_ontology": "entities",
        "orp_role": "Objects",
        "domain_count": 40
    },
    "engineering": {
        "label": "Engineering & Applied Sciences",
        "upper_ontology": "relations",
        "orp_role": "Relations",
        "domain_count": 14
    },
    "social_sciences": {
        "label": "Social Sciences & Human Behavior",
        "upper_ontology": "entities",
        "orp_role": "Objects",
        "domain_count": 20
    },
    "history": {
        "label": "History & Cultural Studies",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 20
    },
    "languages_literature": {
        "label": "Languages & Literature",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 34
    },
    "arts": {
        "label": "Arts, Music & Performance",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 21
    },
    "business_economics": {
        "label": "Business, Economics & Law",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 26
    },
    "health_medicine": {
        "label": "Health & Medicine",
        "upper_ontology": "entities",
        "orp_role": "Objects",
        "domain_count": 15
    },
    "philosophy_religion": {
        "label": "Philosophy, Religion & Ethics",
        "upper_ontology": "relations",
        "orp_role": "Relations",
        "domain_count": 15
    },
    "vocational": {
        "label": "Applied & Vocational Skills",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 12
    },
    "interdisciplinary": {
        "label": "Interdisciplinary & Emerging Fields",
        "upper_ontology": "events_processes",
        "orp_role": "Processes",
        "domain_count": 16
    }
}


def create_upper_ontology_hypernodes() -> List[Dict[str, Any]]:
    """
    Create the 3 Upper Ontology hypernodes (Entities, Relations, Events/Processes).
    
    Returns:
        List of hypernode dicts ready for KG insertion
    """
    hypernodes = []
    
    for ontology_key, ontology_data in UPPER_ONTOLOGY.items():
        # Get category IDs that will be nested in this ontology
        category_ids = []
        for cat_key, cat_data in CATEGORIES.items():
            if cat_data["upper_ontology"] == ontology_key:
                # We'll generate IDs when we create category hypernodes
                category_ids.append(f"CAT:{cat_key}")
        
        hypernode = create_hypernode(
            name=ontology_data["label"],
            scale="macro",
            subgraph_nodes=category_ids,  # Will be populated when categories are created
            orp_structure={
                "objects": category_ids if ontology_data["orp_role"] == "Objects" else [],
                "relations": category_ids if ontology_data["orp_role"] == "Relations" else [],
                "processes": category_ids if ontology_data["orp_role"] == "Processes" else []
            },
            aggregated_properties={
                "upper_ontology_type": ontology_key,
                "orp_role": ontology_data["orp_role"],
                "category_count": len(category_ids),
                "description": ontology_data["description"]
            },
            compression_level=0.8,  # High compression - top level
            fractal_depth=0  # Root level
        )
        
        # Add upper ontology metadata
        hypernode["properties"]["upper_ontology_type"] = ontology_key
        hypernode["properties"]["orp_role"] = ontology_data["orp_role"]
        hypernode["properties"]["level"] = "upper_ontology"
        
        hypernodes.append(hypernode)
        logger.info(f"Created upper ontology hypernode: {ontology_data['label']}")
    
    return hypernodes


def create_category_hypernodes() -> List[Dict[str, Any]]:
    """
    Create the 12 Category hypernodes with ORP structure.
    
    Returns:
        List of hypernode dicts ready for KG insertion
    """
    hypernodes = []
    
    for cat_key, cat_data in CATEGORIES.items():
        # Determine ORP structure based on role
        orp_structure = {
            "objects": [],
            "relations": [],
            "processes": []
        }
        
        if cat_data["orp_role"] == "Objects":
            orp_structure["objects"] = [f"DOMAIN:*"]  # Placeholder for domains
        elif cat_data["orp_role"] == "Relations":
            orp_structure["relations"] = [f"DOMAIN:*"]
        elif cat_data["orp_role"] == "Processes":
            orp_structure["processes"] = [f"DOMAIN:*"]
        
        hypernode = create_hypernode(
            name=cat_data["label"],
            scale="macro",
            subgraph_nodes=[],  # Will contain domain IDs
            orp_structure=orp_structure,
            aggregated_properties={
                "category_key": cat_key,
                "upper_ontology": cat_data["upper_ontology"],
                "orp_role": cat_data["orp_role"],
                "domain_count": cat_data["domain_count"],
                "label": cat_data["label"]
            },
            compression_level=0.6,  # Medium compression
            fractal_depth=1  # One level below upper ontology
        )
        
        # Add category metadata
        hypernode["properties"]["category_key"] = cat_key
        hypernode["properties"]["upper_ontology"] = cat_data["upper_ontology"]
        hypernode["properties"]["orp_role"] = cat_data["orp_role"]
        hypernode["properties"]["level"] = "category"
        
        hypernodes.append(hypernode)
        logger.info(f"Created category hypernode: {cat_data['label']} ({cat_data['orp_role']})")
    
    return hypernodes


def create_category_structure() -> Dict[str, Any]:
    """
    Create complete category structure with upper ontology and categories.
    
    Returns:
        Dict with nodes, edges, and metadata
    """
    # Create upper ontology hypernodes
    upper_ontology_nodes = create_upper_ontology_hypernodes()
    
    # Create category hypernodes
    category_nodes = create_category_hypernodes()
    
    # Create edges: categories nested in upper ontology
    edges = []
    upper_ontology_map = {}  # Map ontology key to hypernode ID
    
    for ontology_node in upper_ontology_nodes:
        ontology_key = ontology_node["properties"]["upper_ontology_type"]
        upper_ontology_map[ontology_key] = ontology_node["id"]
    
    for category_node in category_nodes:
        category_key = category_node["properties"]["category_key"]
        upper_ontology_key = category_node["properties"]["upper_ontology"]
        
        if upper_ontology_key in upper_ontology_map:
            edges.append({
                "from": category_node["id"],
                "to": upper_ontology_map[upper_ontology_key],
                "type": "NESTED_IN",
                "properties": {
                    "nesting_depth": 1,
                    "scale": "macro",
                    "orp_role": category_node["properties"]["orp_role"]
                }
            })
    
    # Create SCALES_TO edges between upper ontology and categories
    for category_node in category_nodes:
        upper_ontology_key = category_node["properties"]["upper_ontology"]
        if upper_ontology_key in upper_ontology_map:
            edges.append({
                "from": category_node["id"],
                "to": upper_ontology_map[upper_ontology_key],
                "type": "SCALES_TO",
                "properties": {
                    "from_scale": "macro",
                    "to_scale": "macro",
                    "self_similarity_score": 0.9,
                    "scaling_type": "category_to_ontology"
                }
            })
    
    return {
        "nodes": upper_ontology_nodes + category_nodes,
        "edges": edges,
        "metadata": {
            "upper_ontology_count": len(upper_ontology_nodes),
            "category_count": len(category_nodes),
            "total_nodes": len(upper_ontology_nodes) + len(category_nodes),
            "total_edges": len(edges)
        }
    }


def create_category_to_domain_edges(domain_node_ids: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Create edges linking domain nodes to their category hypernodes.
    
    Args:
        domain_node_ids: Dict mapping domain names to their node IDs
    
    Returns:
        List of NESTED_IN edges
    """
    edges = []
    
    # Map domain names to categories (simplified - would need full domain taxonomy)
    # This is a placeholder - in production, you'd query the domain taxonomy
    domain_to_category = {
        # Mathematics domains
        "Arithmetic": "mathematics",
        "Algebra": "mathematics",
        "Calculus": "mathematics",
        "Geometry": "mathematics",
        "Statistics": "mathematics",
        "Computer Science": "mathematics",
        
        # Natural Sciences domains
        "Biology": "natural_sciences",
        "Chemistry": "natural_sciences",
        "Physics": "natural_sciences",
        "Earth Science": "natural_sciences",
        
        # Add more mappings as needed
    }
    
    category_hypernode_ids = {}
    for cat_key in CATEGORIES.keys():
        # Generate expected category hypernode ID
        category_hypernode_ids[cat_key] = f"CAT:{cat_key}"
    
    for domain_name, domain_id in domain_node_ids.items():
        # Find category for this domain
        category_key = None
        for domain_pattern, cat in domain_to_category.items():
            if domain_pattern.lower() in domain_name.lower():
                category_key = cat
                break
        
        if category_key and category_key in category_hypernode_ids:
            edges.append({
                "from": domain_id,
                "to": category_hypernode_ids[category_key],
                "type": "NESTED_IN",
                "properties": {
                    "nesting_depth": 2,
                    "scale": "meso",
                    "domain_name": domain_name
                }
            })
    
    return edges


def get_category_by_domain(domain_name: str) -> str | None:
    """
    Get the category key for a given domain name.
    
    Args:
        domain_name: Name of the domain
    
    Returns:
        Category key or None if not found
    """
    # This would ideally query the full domain taxonomy
    # For now, return based on simple matching
    domain_lower = domain_name.lower()
    
    # Mathematics
    if any(term in domain_lower for term in ["math", "algebra", "calculus", "geometry", 
                                              "statistics", "computer science", "programming"]):
        return "mathematics"
    
    # Natural Sciences
    if any(term in domain_lower for term in ["biology", "chemistry", "physics", "earth science",
                                             "astronomy", "geology"]):
        return "natural_sciences"
    
    # Social Sciences
    if any(term in domain_lower for term in ["psychology", "sociology", "political", "geography"]):
        return "social_sciences"
    
    # History
    if "history" in domain_lower:
        return "history"
    
    # Languages & Literature
    if any(term in domain_lower for term in ["language", "literature", "writing", "reading"]):
        return "languages_literature"
    
    # Arts
    if any(term in domain_lower for term in ["art", "music", "theater", "dance", "performance"]):
        return "arts"
    
    # Business & Economics
    if any(term in domain_lower for term in ["business", "economics", "law", "finance"]):
        return "business_economics"
    
    # Health & Medicine
    if any(term in domain_lower for term in ["health", "medicine", "medical", "nursing"]):
        return "health_medicine"
    
    # Philosophy & Religion
    if any(term in domain_lower for term in ["philosophy", "religion", "ethics", "logic"]):
        return "philosophy_religion"
    
    # Vocational
    if any(term in domain_lower for term in ["vocational", "trade", "culinary", "automotive"]):
        return "vocational"
    
    # Interdisciplinary (default for unknown)
    return "interdisciplinary"


def get_upper_ontology_by_category(category_key: str) -> str | None:
    """
    Get the upper ontology key for a given category.
    
    Args:
        category_key: Category key
    
    Returns:
        Upper ontology key or None
    """
    if category_key in CATEGORIES:
        return CATEGORIES[category_key]["upper_ontology"]
    return None


def get_orp_role_by_category(category_key: str) -> str | None:
    """
    Get the ORP role for a given category.
    
    Args:
        category_key: Category key
    
    Returns:
        ORP role (Objects, Relations, or Processes) or None
    """
    if category_key in CATEGORIES:
        return CATEGORIES[category_key]["orp_role"]
    return None
