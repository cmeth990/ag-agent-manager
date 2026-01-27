# Category Structure Implementation

## Overview

This implementation adds the complete category taxonomy structure to the knowledge graph, creating a fractal ORP hierarchy from Upper Ontology → Categories → Domains → Concepts.

## Structure Created

### Level 1: Upper Ontology Hypernodes (3)
1. **Entities** (Objects)
   - Contains: natural_sciences, social_sciences, health_medicine
   - ORP Role: Objects
   - Scale: macro

2. **Relations** (Relations)
   - Contains: mathematics, engineering, philosophy_religion
   - ORP Role: Relations
   - Scale: macro

3. **Events/Processes** (Processes)
   - Contains: history, business_economics, interdisciplinary, languages_literature, arts, vocational
   - ORP Role: Processes
   - Scale: macro

### Level 2: Category Hypernodes (12)
1. Mathematics & Computational Sciences (Relations)
2. Natural Sciences (Objects)
3. Engineering & Applied Sciences (Relations)
4. Social Sciences & Human Behavior (Objects)
5. History & Cultural Studies (Processes)
6. Languages & Literature (Processes)
7. Arts, Music & Performance (Processes)
8. Business, Economics & Law (Processes)
9. Health & Medicine (Objects)
10. Philosophy, Religion & Ethics (Relations)
11. Applied & Vocational Skills (Processes)
12. Interdisciplinary & Emerging Fields (Processes)

## Files Created

### 1. `app/kg/categories.py`
Core module containing:
- `UPPER_ONTOLOGY`: Upper ontology definitions
- `CATEGORIES`: Category definitions with ORP roles
- `create_upper_ontology_hypernodes()`: Generate upper ontology hypernodes
- `create_category_hypernodes()`: Generate category hypernodes
- `create_category_structure()`: Create complete structure with edges
- `get_category_by_domain()`: Map domain names to categories
- `get_upper_ontology_by_category()`: Get upper ontology for category
- `get_orp_role_by_category()`: Get ORP role for category

### 2. `scripts/ingest_categories.py`
Script to ingest category structure into the KG:
```bash
python scripts/ingest_categories.py
```

### 3. Updated Files
- `app/kg/knowledge_base.py`: Added category imports and schema updates
- `app/graph/workers.py`: Added category assignment to concepts during extraction

## Usage

### Ingest Categories into KG

```bash
cd ag-agent-manager
python scripts/ingest_categories.py
```

This will:
1. Create 3 Upper Ontology hypernodes
2. Create 12 Category hypernodes
3. Link categories to upper ontology via NESTED_IN edges
4. Create SCALES_TO edges showing fractal scaling

### Automatic Category Assignment

When extracting concepts, the system now automatically:
1. Detects domain from concept properties
2. Maps domain to category using `get_category_by_domain()`
3. Adds category, upper_ontology, and orp_role properties to concepts
4. Can create NESTED_IN edges to category hypernodes

### Query Categories

```python
from app.kg.client import query_kg

# Query for category hypernodes
results = await query_kg("category:mathematics")

# Query for upper ontology
results = await query_kg("upper ontology:entities")
```

## Edge Types Created

1. **NESTED_IN**: Category → Upper Ontology
   - Properties: nesting_depth=1, scale=macro, orp_role

2. **NESTED_IN**: Domain → Category (created automatically during extraction)
   - Properties: nesting_depth=2, scale=meso, domain_name

3. **SCALES_TO**: Category → Upper Ontology
   - Properties: from_scale=macro, to_scale=macro, self_similarity_score=0.9

## ORP Structure

Each category hypernode has ORP metadata:
```python
{
    "objects": [],  # For Objects categories
    "relations": [],  # For Relations categories
    "processes": []  # For Processes categories
}
```

## Next Steps

1. **Link Existing Domains**: Create script to link existing 175 concepts to categories
2. **Domain Taxonomy Integration**: Import full domain taxonomy from `ComprehensiveDomainTaxonomy.js`
3. **Category Queries**: Add query functions for category-based searches
4. **Visualization**: Add category visualization to KG UI
5. **Validation**: Ensure all domains are properly categorized

## Example Output

After running `ingest_categories.py`:

```
✅ Successfully ingested category structure!
Nodes: +15
Edges: +24

📊 Category Structure Ingested:
  Upper Ontology: 3 hypernodes
  Categories: 12 hypernodes
  Total Edges: 24

🔗 Upper Ontology Hypernodes:
  - Entities (Objects)
    ID: HN:uuid-1
  - Relations (Relations)
    ID: HN:uuid-2
  - Events/Processes (Processes)
    ID: HN:uuid-3

📁 Category Hypernodes:
  - Mathematics & Computational Sciences
    Category: mathematics
    ORP Role: Relations
    Upper Ontology: relations
    ID: HN:uuid-4
  ...
```

## Integration with Extraction

When a concept is extracted with a domain:
- Domain "Algebra" → Category "mathematics" → Upper Ontology "relations" → ORP Role "Relations"
- These properties are automatically added to the concept
- NESTED_IN edge can be created to category hypernode

This completes the fractal structure: Concept (micro) → Domain (meso) → Category (macro) → Upper Ontology (macro+).
