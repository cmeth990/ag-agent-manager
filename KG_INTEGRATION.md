# Knowledge Graph Integration Summary

This document describes how the ag-agent-manager has been integrated with the knowledge graph documents from the LUMI_3 folder.

## What Was Integrated

### 1. Knowledge Base Module (`app/kg/knowledge_base.py`)

Created a comprehensive knowledge base that captures:
- **Node Types**: Concept, Claim, Position, Evidence, Source, Method, Scope
- **Edge Types**: DEFINES, SUPPORTS/REFUTES, PREREQ, PartOf, IsA, RELATED_TO, etc.
- **ID Format**: Proper prefixes (C:, CL:, E:, SRC:, M:, S:, PO:) with UUID
- **Current KG State**: 175 concepts, 615 edges, 100% metadata coverage
- **Validation Rules**: Minimum support, completeness thresholds, acyclic requirements
- **Scoring Information**: TruthScore, SupportScore, CompletenessScore formulas

### 2. Enhanced Extraction (`app/graph/workers.py`)

**Updated Extraction Prompt:**
- Now understands the Agnosia KG schema
- Knows about proper node types (Concept, Claim, Evidence, etc.)
- Uses correct edge types (DEFINES, PrerequisiteOf, PartOf, etc.)
- Generates IDs with proper prefixes (C:uuid format)

**Improved Entity Processing:**
- Validates and fixes ID formats
- Maps entity labels to proper KG node types
- Uses knowledge base for schema-aware processing

**Enhanced Linking:**
- KG-aware entity matching
- Proper canonical ID mapping
- Node type inference from IDs

**Better Diff Generation:**
- Uses proper KG node labels (Concept, Claim, etc.)
- Validates edge types against known types
- Maps common edge types to KG schema

### 3. Enhanced KG Client (`app/kg/client.py`)

**Schema-Aware Operations:**
- Validates node labels against known types
- Infers node types from IDs
- Supports all KG node types in queries
- Proper Neo4j label usage (Concept, Claim, Evidence, etc.)

**Improved Queries:**
- Searches across multiple property fields (name, text, title, description)
- Returns proper node types and IDs
- Better result formatting

## Key Features

### ID Format
- **Before**: `entity_abc123` or generic IDs
- **After**: `C:123e4567-e89b-12d3-a456-426614174000` (proper KG format)

### Node Types
- **Before**: Generic "Entity", "Person", "Topic"
- **After**: Proper KG types: "Concept", "Claim", "Evidence", "Source", "Method", "Scope", "Position"

### Edge Types
- **Before**: Generic "STUDIES", "WORKS_ON"
- **After**: KG schema edges: "DEFINES", "PrerequisiteOf", "PartOf", "IsA", "SUPPORTS", etc.

### Schema Awareness
- Extraction prompt includes full KG schema
- Workers validate against schema
- Client uses proper Neo4j labels
- All operations respect KG structure

## Current KG Context

The agent now knows:
- **175 concepts** exist in the KG
- **615 edges** (3.51 per concept)
- **100% metadata and definition coverage**
- Edge type distribution (RelatedTo: 66.3%, PrerequisiteOf: 27.5%, PartOf: 6.2%)
- Validation requirements (≥2 supports, ≥80% completeness)
- Scoring formulas (TruthScore, SupportScore)

## Usage Examples

### Example 1: Simple Topic Ingestion
```
User: /ingest topic=photosynthesis
```

**Before**: Would create generic "Topic" entity with random ID
**After**: Creates "Concept" node with ID `C:uuid`, proper domain, and schema-compliant structure

### Example 2: Complex Extraction
```
User: /ingest Photosynthesis is the process by which plants convert CO2 to glucose. It requires sunlight and chlorophyll.
```

**Before**: Generic entities and relations
**After**: 
- Concept node: "Photosynthesis" (C:uuid)
- Claim node: "Photosynthesis converts CO2 to glucose" (CL:uuid)
- DEFINES edge: Claim → Concept
- Proper domain assignment

### Example 3: Query
```
User: /query photosynthesis
```

**Before**: Basic keyword search
**After**: Schema-aware search across Concept.name, Claim.text, Evidence.content, etc.

## Files Modified

1. **app/kg/knowledge_base.py** (NEW)
   - Complete KG schema and knowledge base

2. **app/graph/workers.py**
   - Updated extraction prompt with KG schema
   - Enhanced entity processing with ID validation
   - Improved linking with KG awareness
   - Better diff generation

3. **app/kg/client.py**
   - Schema-aware node creation
   - Improved query support
   - Proper label handling

## Next Steps (Optional Enhancements)

1. **Completeness Checking**: Add completeness score calculation before committing
2. **Validation**: Implement validation rules (≥2 supports, acyclic PREREQ)
3. **Scoring**: Add TruthScore calculation for claims
4. **Edge Discovery**: Enhance edge type inference (detect PrerequisiteOf, PartOf automatically)
5. **Metadata Extraction**: Infer domain, difficulty, grade_level from content
6. **KG Statistics**: Add command to show current KG state (175 concepts, etc.)

## Testing

To test the integration:

```bash
cd ag-agent-manager
python -m pytest tests/  # If tests exist
# Or manually test via Telegram bot
```

The agent should now:
- Extract entities with proper KG node types
- Generate IDs in correct format (C:uuid)
- Use proper edge types (DEFINES, PrerequisiteOf, etc.)
- Link to existing KG entities when possible
- Create schema-compliant diffs

## References

- **KG Schema**: `src/mapmaker/kg/docs/AGNOSIA_KG_SUMMARY.md`
- **KG Analysis**: `src/mapmaker/kg/KNOWLEDGE_GRAPH_ANALYSIS.md`
- **Node Models**: `src/mapmaker/kg/src/models/nodes.js`
- **Edge Models**: `src/mapmaker/kg/src/models/edges.js`
- **Schema JSON**: `src/mapmaker/kg/schemas/concept_profile.schema.json`
