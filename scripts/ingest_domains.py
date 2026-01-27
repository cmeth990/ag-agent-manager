#!/usr/bin/env python3
"""
Script to ingest all domains into the knowledge graph.
Links domains to their category hypernodes.
"""
import sys
import os
import asyncio
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kg.domains import create_all_domains, get_domains_by_category
from app.kg.client import apply_diff, query_kg
from app.kg.diff import create_empty_diff, format_diff_summary
from app.kg.categories import CATEGORIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_category_hypernode_ids():
    """Query KG to get actual category hypernode IDs."""
    category_ids = {}
    
    for category_key in CATEGORIES.keys():
        # Query for category hypernode
        results = await query_kg(f"category:{category_key}")
        if results:
            for result in results:
                props = result.get("properties", {})
                if props.get("category_key") == category_key:
                    category_ids[category_key] = result.get("node_id")
                    break
        
        # If not found, use expected ID format
        if category_key not in category_ids:
            category_ids[category_key] = f"CAT:{category_key}"
            logger.warning(f"Category {category_key} not found in KG, using expected ID")
    
    return category_ids


async def ingest_domains(batch_size: int = 50):
    """Ingest all domains into the knowledge graph in batches."""
    logger.info("Creating domain structure...")
    
    # Get actual category hypernode IDs from KG first
    logger.info("Querying category hypernode IDs...")
    category_ids = await get_category_hypernode_ids()
    
    # Create all domains with actual category IDs
    domain_structure = create_all_domains(category_hypernode_ids=category_ids)
    
    total_domains = len(domain_structure["nodes"])
    total_edges = len(domain_structure["edges"])
    
    logger.info(f"Generated {total_domains} domain nodes and {total_edges} edges")
    
    # Process in batches
    all_nodes = domain_structure["nodes"]
    all_edges = domain_structure["edges"]
    
    batches = []
    for i in range(0, len(all_nodes), batch_size):
        batch_nodes = all_nodes[i:i + batch_size]
        # Get edges for these nodes
        node_ids = {node["id"] for node in batch_nodes}
        batch_edges = [e for e in all_edges if e["from"] in node_ids]
        
        batches.append({
            "nodes": batch_nodes,
            "edges": batch_edges
        })
    
    logger.info(f"Processing {len(batches)} batches...")
    
    total_added = 0
    total_errors = 0
    
    for batch_num, batch in enumerate(batches, 1):
        logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch['nodes'])} nodes, {len(batch['edges'])} edges)...")
        
        # Create diff
        diff = create_empty_diff()
        diff["nodes"]["add"] = batch["nodes"]
        diff["edges"]["add"] = batch["edges"]
        diff["metadata"]["source"] = "domain_taxonomy_ingestion"
        diff["metadata"]["reason"] = f"Batch {batch_num}: Ingest domains for categories"
        
        # Apply diff
        result = await apply_diff(diff)
        
        if result.get("success"):
            added = result["nodes"]["added"]
            total_added += added
            logger.info(f"✅ Batch {batch_num}: Added {added} nodes, {result['edges']['added']} edges")
        else:
            total_errors += len(batch["nodes"])
            logger.error(f"❌ Batch {batch_num} failed: {result.get('errors', [])}")
    
    # Print summary
    print("\n" + "="*60)
    print("📊 Domain Ingestion Summary")
    print("="*60)
    print(f"Total Domains: {total_domains}")
    print(f"Successfully Added: {total_added}")
    print(f"Errors: {total_errors}")
    print(f"Total Edges: {total_edges}")
    
    print("\n📁 Domains by Category:")
    for category_key, category_data in CATEGORIES.items():
        domains = get_domains_by_category(category_key)
        print(f"  {category_data['label']}: {len(domains)} domains")
    
    return total_added == total_domains


if __name__ == "__main__":
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    success = asyncio.run(ingest_domains(batch_size=batch_size))
    sys.exit(0 if success else 1)
