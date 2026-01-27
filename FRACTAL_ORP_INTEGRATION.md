# Fractal ORP Knowledge Graph Integration

This document describes the integration of fractal knowledge graph structure with hypernodes and ORP (Object-Relation-Process) modeling into the ag-agent-manager.

## Overview

The fractal ORP structure enables:
- **Self-similarity**: Patterns repeat across scales (micro → meso → macro)
- **Hypernodes**: Meta-nodes that encapsulate subgraphs, enabling infinite nesting
- **ORP Modeling**: Objects (building blocks), Relations (connectors), Processes (dynamic flows)
- **Fractal Navigation**: Zoom in/out, drill down, scale queries

## Architecture

### Node Types Added

1. **Hypernode (HN:uuid)**
   - Encapsulates subgraphs
   - Properties: `name`, `scale`, `subgraph_nodes`, `subgraph_edges`, `compression_level`, `fractal_depth`, `orp_structure`
   - Enables fractal nesting (hypernodes can contain other hypernodes)

2. **Process (P:uuid)**
   - Dynamic flows/transformations in ORP model
   - Properties: `name`, `processType`, `inputs`, `outputs`, `scale`, `transformation`
   - Represents processes that transform objects/relations

### Edge Types Added

**Fractal ORP Edges:**
- `CONTAINS`: Hypernode → Node (hypernode contains subgraph)
- `NESTED_IN`: Node → Hypernode (node nested in hypernode)
- `AGGREGATES`: Hypernode → Node (aggregates properties)
- `ENABLES`: Process → Node (process enables transformation)
- `INPUTS_TO`: Node → Process (object/relation inputs to process)
- `OUTPUTS_FROM`: Process → Node (process outputs object/relation)
- `SCALES_TO`: Node → Node (fractal scaling: micro → meso → macro)
- `MIRRORS`: Node ↔ Node (self-similar patterns at different scales)

## ORP Scales

### Micro (Individual Concept Claims)
- **Objects**: Atomic elements (facts, terms, e.g., "Voltage Bias")
- **Relations**: Links defining interactions (e.g., "Applies To")
- **Processes**: Dynamic flows (e.g., "Signal Propagation")
- **Example**: Single claim with evidence nodes

### Meso (Concept Clusters / Domain Subgraphs)
- **Objects**: Aggregated micro-objects (e.g., "Gate" hypernode)
- **Relations**: Scaled connectors (e.g., "Series/Parallel Wiring")
- **Processes**: Emergent inputs/outputs (e.g., "Boolean Evaluation")
- **Example**: Logic gate subgraph nesting transistor claims

### Macro (Meta-Categories / Overarching Domains)
- **Objects**: High-level hypernodes (e.g., "Computational Hierarchy")
- **Relations**: Broad enablers (e.g., "Hierarchical Emanation")
- **Processes**: Global flows (e.g., "Recursive Scaling")
- **Example**: Knowledge domain nesting all subgraphs

## Implementation

### 1. Knowledge Base (`app/kg/knowledge_base.py`)

Added:
- `Hypernode` and `Process` node types
- ORP edge types (CONTAINS, NESTED_IN, ENABLES, INPUTS_TO, OUTPUTS_FROM, SCALES_TO, MIRRORS)
- `ORP_SCALES` dictionary (micro, meso, macro)
- `FRACTAL_PROPERTIES` documentation
- Updated `SCHEMA_SUMMARY` with fractal ORP information

### 2. Hypernode Operations (`app/kg/hypernode.py`)

**Functions:**
- `create_hypernode()`: Create hypernode with subgraph encapsulation
- `create_process_node()`: Create Process node for ORP modeling
- `create_orp_structure()`: Create complete ORP structure with objects, relations, processes
- `detect_orp_pattern()`: Detect ORP patterns in subgraph
- `infer_scale_from_content()`: Infer ORP scale from content
- `create_fractal_scaling_edge()`: Create SCALES_TO edge
- `create_mirror_edge()`: Create MIRRORS edge

### 3. KG Client (`app/kg/client.py`)

**New Functions:**
- `expand_hypernode()`: Expand hypernode to show contained subgraph
- `query_fractal_scale()`: Query fractal scaling relationships (micro → meso → macro)
- `query_orp_structure()`: Query ORP structure around a node

### 4. Extraction (`app/graph/workers.py`)

**Enhanced Extraction Prompt:**
- Understands Hypernode and Process node types
- Recognizes ORP edge types
- Detects scale (micro, meso, macro)
- Identifies ORP patterns (objects, relations, processes)
- Creates hypernodes for clusters automatically

**Worker Updates:**
- `writer_node()`: Automatically creates hypernodes for clusters (5+ nodes)
- Detects ORP patterns and structures them
- Adds scale properties to nodes
- Creates CONTAINS edges from hypernodes

### 5. Query Node (`app/graph/workers.py`)

**Fractal Navigation Commands:**
- `/query expand <hypernode_id>` - Expand hypernode to show subgraph
- `/query scale to <node_id> <micro|meso|macro>` - Query fractal scaling
- `/query orp <node_id>` - View ORP structure (objects, relations, processes)

## Usage Examples

### Example 1: Automatic Hypernode Creation

```
User: /ingest Logic gates are composed of transistors. A gate performs boolean evaluation.
```

**Extraction:**
- Concept: "Logic Gate" (C:uuid)
- Concept: "Transistor" (C:uuid)
- Process: "Boolean Evaluation" (P:uuid)
- Hypernode: "Logic Gate Cluster" (HN:uuid, scale: meso)
- Edges: CONTAINS (hypernode → concepts), INPUTS_TO (concepts → process), OUTPUTS_FROM (process → concepts)

### Example 2: Fractal Scaling

```
User: /query scale to C:transistor_id macro
```

**Result:**
- Finds nodes at macro scale connected via SCALES_TO edges
- Shows how micro (transistor) scales to macro (computational hierarchy)

### Example 3: ORP Structure Query

```
User: /query orp HN:gate_cluster_id
```

**Result:**
- Objects: Concepts, Claims, Evidence in the cluster
- Relations: Edges between objects
- Processes: Process nodes with inputs/outputs

### Example 4: Expand Hypernode

```
User: /query expand HN:domain_cluster_id
```

**Result:**
- Shows all nodes contained in hypernode
- Shows edges between contained nodes
- Enables drill-down navigation

## Benefits

1. **Scalability**: Infinite nesting via hypernodes
2. **Modularity**: Subgraphs encapsulated and reusable
3. **Emergent Insights**: Patterns emerge at different scales
4. **Navigability**: Zoom in/out without losing coherence
5. **Self-Similarity**: ORP structure repeats at every scale
6. **Resilience**: Local changes propagate consistently

## Fractal Properties

- **Self-Similarity**: Patterns repeat across scales (micro → meso → macro)
- **Hypernode Nesting**: Hypernodes can contain other hypernodes (infinite depth)
- **ORP Repetition**: ORP structure repeats at every scale
- **Zoom Capability**: Navigate micro → meso → macro seamlessly
- **Emergent Properties**: Macro properties emerge from micro interactions

## Mathematical Foundation

The fractal structure is mathematically grounded:
- **Graph Theory**: Hypernodes as subgraph containers
- **Fractal Geometry**: Self-similar patterns at different scales
- **ORP Algebra**: Objects, Relations, Processes as algebraic structures
- **Recursion**: Nested structures enable recursive queries

## Next Steps

1. **Visualization**: Add fractal graph visualization (zoom in/out UI)
2. **Auto-Detection**: Enhance ORP pattern detection in extraction
3. **Scale Inference**: Improve scale inference from content
4. **Mirror Detection**: Automatically detect self-similar patterns
5. **Aggregation**: Auto-aggregate properties from subgraphs to hypernodes
6. **Validation**: Add validation for fractal structure (acyclic containment, etc.)

## References

- **Fractal Theory**: Mandelbrot sets, self-similarity
- **Graph Theory**: Hypergraphs, nested subgraphs
- **ORP Model**: Object-Relation-Process modeling
- **Knowledge Representation**: Hierarchical knowledge structures
