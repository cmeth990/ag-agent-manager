# Domain Population Implementation

## Overview

This implementation populates all 287 domains from the knowledge taxonomy into the knowledge graph, linking each domain to its category hypernode.

## Domain Structure

Each domain is created as a **Concept node at meso scale** with:
- **Properties**: name, domain, category, upper_ontology, orp_role, gradebands, difficulty
- **Scale**: meso (domains are at the meso level in the fractal hierarchy)
- **Level**: domain
- **Metadata**: gradebands, difficulty, domain_type

## Domain Count by Category

Based on the taxonomy:

| Category | Domain Count | Examples |
|----------|--------------|----------|
| Mathematics | 44 | Arithmetic, Algebra, Calculus, Computer Science |
| Natural Sciences | 40+ | Biology, Chemistry, Physics, Earth Science |
| Engineering | 14 | Mechanical, Electrical, Civil, Robotics |
| Social Sciences | 20+ | Psychology, Sociology, Political Science |
| History | 20+ | Ancient History, World History, Cultural Studies |
| Languages & Literature | 34 | English, Literature, Linguistics, World Languages |
| Arts | 21 | Art, Music, Theater, Dance, Film |
| Business & Economics | 26 | Economics, Business, Law, Finance |
| Health & Medicine | 15+ | Medicine, Nursing, Public Health |
| Philosophy & Religion | 15+ | Philosophy, Ethics, Logic, Religion |
| Vocational | 12 | Culinary Arts, Automotive, Construction |
| Interdisciplinary | 16 | Environmental Studies, Data Science, Education |

**Total: ~287 domains**

## Files Created

### 1. `app/kg/domains.py`
Core domain module with:
- `DOMAIN_TAXONOMY`: Complete domain taxonomy for all 12 categories
- `create_domain_node()`: Generate domain nodes with full metadata
- `create_domain_structure_for_category()`: Create all domains for a category
- `create_all_domains()`: Create all 287 domains
- `get_domain_by_name()`: Lookup domain information
- `get_domains_by_category()`: Get domains for a category
- `get_domains_by_gradeband()`: Filter by grade level
- `get_domains_by_difficulty()`: Filter by difficulty

### 2. `scripts/ingest_domains.py`
Bulk domain ingestion script:
- Queries category hypernode IDs from KG
- Creates all domain nodes
- Links domains to categories via NESTED_IN edges
- Processes in batches (default 50 per batch)

### 3. `scripts/parse_domain_taxonomy.py`
Parser to extract domains from JavaScript taxonomy file (optional)

## Usage

### Ingest All Domains

```bash
cd ag-agent-manager
python scripts/ingest_domains.py [batch_size]
```

This will:
1. Query category hypernode IDs from KG
2. Create all 287 domain nodes
3. Link each domain to its category via NESTED_IN edge
4. Process in batches (default: 50 domains per batch)

### Example Output

```
Creating domain structure...
Querying category hypernode IDs...
Generated 287 domain nodes and 287 edges
Processing 6 batches...

✅ Batch 1: Added 50 nodes, 50 edges
✅ Batch 2: Added 50 nodes, 50 edges
...

📊 Domain Ingestion Summary
============================================================
Total Domains: 287
Successfully Added: 287
Errors: 0
Total Edges: 287

📁 Domains by Category:
  Mathematics & Computational Sciences: 44 domains
  Natural Sciences: 40 domains
  Engineering & Applied Sciences: 14 domains
  ...
```

## Domain Node Structure

Each domain node:
```python
{
    "id": "C:uuid",
    "label": "Concept",
    "properties": {
        "id": "C:uuid",
        "name": "Algebra",
        "domain": "Algebra",
        "category": "mathematics",
        "upper_ontology": "relations",
        "orp_role": "Relations",
        "scale": "meso",
        "level": "domain",
        "gradebands": ["6-8", "9-12"],
        "difficulty": "intermediate",
        "metadata": {
            "domain_type": "knowledge_domain",
            "category_key": "mathematics",
            "gradebands": ["6-8", "9-12"],
            "difficulty": "intermediate"
        }
    }
}
```

## Edge Structure

Each domain → category edge:
```python
{
    "from": "C:domain_uuid",
    "to": "HN:category_uuid",
    "type": "NESTED_IN",
    "properties": {
        "nesting_depth": 2,
        "scale": "meso",
        "domain_name": "Algebra",
        "category_key": "mathematics"
    }
}
```

## Complete Hierarchy

After ingestion, the fractal structure is complete:

```
Upper Ontology (macro+)
  └── Category Hypernode (macro)
      └── Domain Node (meso) ← NESTED_IN edge
          └── Concept Node (micro) ← Future concepts will link here
```

## Integration with Extraction

When extracting concepts:
- If domain matches a known domain name, automatically:
  - Links to domain node via NESTED_IN or PartOf
  - Inherits category, upper_ontology, orp_role
  - Gets gradebands and difficulty context

## Query Examples

```python
# Get all domains in a category
from app.kg.domains import get_domains_by_category
domains = get_domains_by_category("mathematics")  # Returns 44 domain names

# Get domain info
from app.kg.domains import get_domain_by_name
info = get_domain_by_name("Algebra")
# Returns: category, gradebands, difficulty, upper_ontology, orp_role

# Query KG for domains
results = await query_kg("domain:Algebra")
# Returns domain node with full metadata
```

## Next Steps

1. **Link Existing Concepts**: Create script to link existing 175 concepts to domains
2. **Domain Validation**: Ensure all concepts have valid domain assignments
3. **Domain Queries**: Add query functions for domain-based searches
4. **Domain Statistics**: Track domain coverage and completeness
5. **Sub-domain Support**: Add sub-domain level if needed

## Statistics

After full population:
- **287 domain nodes** (Concept type, meso scale)
- **287 NESTED_IN edges** (domain → category)
- **12 categories** populated
- **3 upper ontologies** connected

This completes the domain layer of the fractal ORP structure!
