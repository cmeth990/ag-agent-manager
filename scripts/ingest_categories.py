#!/usr/bin/env python3
"""
Script to ingest category structure (Upper Ontology + Categories) into the knowledge graph.
"""
import sys
import os
import asyncio
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kg.categories import create_category_structure
from app.kg.client import apply_diff
from app.kg.diff import create_empty_diff, format_diff_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def ingest_categories():
    """Ingest category structure into the knowledge graph."""
    logger.info("Creating category structure...")
    
    # Create the complete category structure
    structure = create_category_structure()
    
    logger.info(f"Generated {structure['metadata']['total_nodes']} nodes and "
                f"{structure['metadata']['total_edges']} edges")
    
    # Create diff
    diff = create_empty_diff()
    diff["nodes"]["add"] = structure["nodes"]
    diff["edges"]["add"] = structure["edges"]
    diff["metadata"]["source"] = "category_taxonomy_ingestion"
    diff["metadata"]["reason"] = "Initialize category structure with upper ontology and categories"
    
    logger.info(f"Diff summary: {format_diff_summary(diff)}")
    
    # Apply diff to KG
    logger.info("Applying diff to knowledge graph...")
    result = await apply_diff(diff)
    
    if result.get("success"):
        logger.info("✅ Successfully ingested category structure!")
        logger.info(f"Nodes: +{result['nodes']['added']}")
        logger.info(f"Edges: +{result['edges']['added']}")
        
        # Print structure
        print("\n📊 Category Structure Ingested:")
        print(f"  Upper Ontology: {structure['metadata']['upper_ontology_count']} hypernodes")
        print(f"  Categories: {structure['metadata']['category_count']} hypernodes")
        print(f"  Total Edges: {structure['metadata']['total_edges']}")
        
        print("\n🔗 Upper Ontology Hypernodes:")
        for node in structure["nodes"]:
            if node.get("properties", {}).get("level") == "upper_ontology":
                print(f"  - {node['properties']['name']} ({node['properties']['orp_role']})")
                print(f"    ID: {node['id']}")
        
        print("\n📁 Category Hypernodes:")
        for node in structure["nodes"]:
            if node.get("properties", {}).get("level") == "category":
                props = node.get("properties", {})
                print(f"  - {props['label']}")
                print(f"    Category: {props['category_key']}")
                print(f"    ORP Role: {props['orp_role']}")
                print(f"    Upper Ontology: {props['upper_ontology']}")
                print(f"    ID: {node['id']}")
        
        return True
    else:
        logger.error("❌ Failed to ingest category structure")
        logger.error(f"Errors: {result.get('errors', [])}")
        return False


if __name__ == "__main__":
    asyncio.run(ingest_categories())
