"""
Knowledge Graph Knowledge Base
Contains schema, node types, edge types, and current KG state information
from the LUMI_3 knowledge graph documents.
"""

# Node Types and ID Prefixes
NODE_TYPES = {
    "Concept": {
        "prefix": "C",
        "description": "Core knowledge unit with definitions and relations",
        "required_properties": ["name", "domain"],
        "optional_properties": ["definitions", "operationalizations", "misconceptions", "relations", "metadata"]
    },
    "Claim": {
        "prefix": "CL",
        "description": "Evidence-backed statement (definition, empirical, theoretical, etc.)",
        "required_properties": ["text", "claimType"],
        "optional_properties": ["scope", "confidence", "supports", "refutations", "sourceId", "conceptId"]
    },
    "Position": {
        "prefix": "PO",
        "description": "Normative stance with supporting arguments",
        "required_properties": ["statement", "domain"],
        "optional_properties": ["arguments", "supportScore", "diversityScore", "metadata"]
    },
    "Evidence": {
        "prefix": "E",
        "description": "Empirical or theoretical support for claims",
        "required_properties": ["type", "content"],
        "optional_properties": ["sourceId", "methodId", "strength", "sampleSize", "effectSize", "pValue"]
    },
    "Source": {
        "prefix": "SRC",
        "description": "Academic papers, books, expert opinions",
        "required_properties": ["title"],
        "optional_properties": ["authors", "year", "type", "doi", "url", "trustScore", "impactFactor"]
    },
    "Method": {
        "prefix": "M",
        "description": "Research methodology used in evidence",
        "required_properties": ["name", "type"],
        "optional_properties": ["description", "validity", "reliability", "limitations"]
    },
    "Scope": {
        "prefix": "S",
        "description": "Context and constraints for claims",
        "required_properties": ["domain"],
        "optional_properties": ["context", "constraints", "temporalRange", "spatialRange", "population"]
    },
    "Hypernode": {
        "prefix": "HN",
        "description": "Meta-node that encapsulates a subgraph, enabling fractal structure",
        "required_properties": ["name", "scale"],
        "optional_properties": [
            "subgraph_nodes",  # List of node IDs contained in this hypernode
            "subgraph_edges",  # List of edge IDs contained in this hypernode
            "compression_level",  # How much detail is hidden (0-1)
            "fractal_depth",  # Nesting depth
            "orp_structure",  # ORP metadata: {objects: [], relations: [], processes: []}
            "aggregated_properties"  # Properties aggregated from subgraph
        ]
    },
    "Process": {
        "prefix": "P",
        "description": "Dynamic flow or transformation in ORP model",
        "required_properties": ["name", "processType"],
        "optional_properties": [
            "inputs",  # List of input node IDs
            "outputs",  # List of output node IDs
            "transformation",  # Description of transformation
            "scale"  # micro, meso, or macro
        ]
    }
}

# Edge Types
EDGE_TYPES = {
    # Agnosia KG Core Edges
    "DEFINES": {
        "description": "Claim defines concept",
        "directional": True,
        "from_types": ["Claim"],
        "to_types": ["Concept"],
        "properties": ["strength", "primary"]
    },
    "UNDER_SCOPE": {
        "description": "Node operates within scope",
        "directional": True,
        "from_types": ["Claim", "Concept", "Evidence"],
        "to_types": ["Scope"],
        "properties": ["applicability"]
    },
    "SUPPORTS": {
        "description": "Evidence supports claim",
        "directional": True,
        "from_types": ["Evidence"],
        "to_types": ["Claim"],
        "properties": ["strength", "methodology", "replicationStatus"]
    },
    "REFUTES": {
        "description": "Evidence refutes claim",
        "directional": True,
        "from_types": ["Evidence"],
        "to_types": ["Claim"],
        "properties": ["strength", "methodology", "replicationStatus"]
    },
    "CONTRADICTS": {
        "description": "Claims contradict each other",
        "directional": False,
        "from_types": ["Claim"],
        "to_types": ["Claim"],
        "properties": ["contradictionType", "strength", "scopeOverlap"]
    },
    "PREREQ": {
        "description": "Prerequisite relationship between concepts",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["necessity", "pedagogical"]
    },
    "RELATED_TO": {
        "description": "General relationship between concepts",
        "directional": False,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["relationshipType", "strength"]
    },
    # Educational Domain Edges (from Relator agent)
    "PrerequisiteOf": {
        "description": "Must be learned before (educational progression)",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["necessity", "pedagogical"]
    },
    "PartOf": {
        "description": "Component or subtopic of",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "IsA": {
        "description": "Specialization or instance of",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "EquivalentTo": {
        "description": "Same concept, different representation",
        "directional": False,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "AlignsWith": {
        "description": "Related or corresponds to",
        "directional": False,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "ComplementaryTo": {
        "description": "Concepts that support each other",
        "directional": False,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "ApplicationOf": {
        "description": "Applies or references",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["weight"]
    },
    "DERIVED_FROM": {
        "description": "Concept derived from another",
        "directional": True,
        "from_types": ["Concept"],
        "to_types": ["Concept"],
        "properties": ["derivationType", "transformations"]
    },
    "USES_METHOD": {
        "description": "Evidence uses a research method",
        "directional": True,
        "from_types": ["Evidence"],
        "to_types": ["Method"],
        "properties": ["adherence", "modifications"]
    },
    "CITES": {
        "description": "Node cites a source",
        "directional": True,
        "from_types": ["Claim", "Evidence", "Position"],
        "to_types": ["Source"],
        "properties": ["citationType", "location"]
    },
    # Fractal ORP Edge Types
    "CONTAINS": {
        "description": "Hypernode contains subgraph nodes (nesting relationship)",
        "directional": True,
        "from_types": ["Hypernode"],
        "to_types": ["Concept", "Claim", "Evidence", "Hypernode", "Process"],
        "properties": ["containment_type", "compression_level"]
    },
    "NESTED_IN": {
        "description": "Node is nested within a hypernode (reverse of CONTAINS)",
        "directional": True,
        "from_types": ["Concept", "Claim", "Evidence", "Hypernode", "Process"],
        "to_types": ["Hypernode"],
        "properties": ["nesting_depth", "scale"]
    },
    "AGGREGATES": {
        "description": "Hypernode aggregates properties from subgraph",
        "directional": True,
        "from_types": ["Hypernode"],
        "to_types": ["Concept", "Claim", "Evidence"],
        "properties": ["aggregation_type", "weight"]
    },
    "ENABLES": {
        "description": "Process enables or transforms objects/relations (ORP model)",
        "directional": True,
        "from_types": ["Process"],
        "to_types": ["Concept", "Claim", "Evidence", "Process"],
        "properties": ["transformation_type", "scale", "strength"]
    },
    "INPUTS_TO": {
        "description": "Object/relation inputs to a process (ORP model)",
        "directional": True,
        "from_types": ["Concept", "Claim", "Evidence", "Process"],
        "to_types": ["Process"],
        "properties": ["input_type", "scale", "weight"]
    },
    "OUTPUTS_FROM": {
        "description": "Process outputs object/relation (ORP model)",
        "directional": True,
        "from_types": ["Process"],
        "to_types": ["Concept", "Claim", "Evidence", "Process"],
        "properties": ["output_type", "scale", "strength"]
    },
    "SCALES_TO": {
        "description": "Fractal scaling relationship (micro → meso → macro)",
        "directional": True,
        "from_types": ["Concept", "Claim", "Hypernode", "Process"],
        "to_types": ["Concept", "Claim", "Hypernode", "Process"],
        "properties": ["from_scale", "to_scale", "self_similarity_score"]
    },
    "MIRRORS": {
        "description": "Self-similar pattern at different scales (fractal mirroring)",
        "directional": False,
        "from_types": ["Concept", "Claim", "Hypernode", "Process"],
        "to_types": ["Concept", "Claim", "Hypernode", "Process"],
        "properties": ["mirror_scale", "similarity_score", "pattern_type"]
    }
}

# Current KG State (from KNOWLEDGE_GRAPH_ANALYSIS.md)
KG_STATE = {
    "concepts": 175,
    "edges": 615,
    "edges_per_concept": 3.51,
    "metadata_coverage": 1.0,  # 100%
    "definition_coverage": 1.0,  # 100%
    "edge_type_distribution": {
        "RelatedTo": 0.663,  # 66.3%
        "PrerequisiteOf": 0.275,  # 27.5%
        "PartOf": 0.062,  # 6.2%
    }
}

# Validation Rules
VALIDATION_RULES = {
    "minimum_support": {
        "description": "≥2 independent supports per definition",
        "required": True
    },
    "scope_consistency": {
        "description": "CONTRADICTS must share scope",
        "required": True
    },
    "prerequisite_acyclic": {
        "description": "PREREQ relationships must be acyclic",
        "required": True
    },
    "completeness_threshold": {
        "description": "≥80% completeness required for publishing",
        "threshold": 0.80,
        "required": True
    }
}

# Completeness Components
COMPLETENESS_COMPONENTS = [
    "definitions",
    "evidence",
    "scope",
    "operationalizations",
    "relations",
    "misconceptions",
    "provenance"
]

# Scoring Information
SCORING = {
    "TruthScore": {
        "formula": "SourceTrust + EvidenceStrength + ReplicationCred + Coherence - ConflictPenalty - Staleness",
        "range": [0, 1],
        "applies_to": ["Claim"]
    },
    "SupportScore": {
        "formula": "Based on argument diversity and strength",
        "range": [0, 1],
        "applies_to": ["Position"]
    },
    "CompletenessScore": {
        "formula": "Weighted average of completeness components",
        "range": [0, 1],
        "applies_to": ["Concept"]
    }
}

# ID Format Helper
def generate_id(node_type: str) -> str:
    """Generate ID in format: PREFIX:uuid"""
    import uuid
    if node_type not in NODE_TYPES:
        raise ValueError(f"Unknown node type: {node_type}")
    prefix = NODE_TYPES[node_type]["prefix"]
    return f"{prefix}:{uuid.uuid4()}"


def validate_id(node_id: str) -> bool:
    """Validate ID format matches expected pattern"""
    if not node_id or ":" not in node_id:
        return False
    prefix, rest = node_id.split(":", 1)
    # Check if prefix matches a known node type
    for node_type, info in NODE_TYPES.items():
        if info["prefix"] == prefix:
            # Check if rest looks like UUID (36 chars with hyphens)
            if len(rest) == 36 and rest.count("-") == 4:
                return True
    return False


def get_node_type_from_id(node_id: str) -> str | None:
    """Get node type from ID prefix"""
    if not node_id or ":" not in node_id:
        return None
    prefix = node_id.split(":")[0]
    for node_type, info in NODE_TYPES.items():
        if info["prefix"] == prefix:
            return node_type
    return None


# ORP Model Scales
ORP_SCALES = {
    "micro": {
        "description": "Individual concept claims - atomic ORP structures",
        "example": "Single claim with evidence (Object: claim, Relation: supports, Process: validation)"
    },
    "meso": {
        "description": "Concept clusters/domain subgraphs - aggregated ORP",
        "example": "Gate subgraph (Object: gate hypernode, Relation: wiring, Process: boolean evaluation)"
    },
    "macro": {
        "description": "Meta-categories/overarching domains - top-level ORP",
        "example": "Computational hierarchy (Object: domain hypernode, Relation: hierarchical emanation, Process: recursive scaling)"
    }
}

# Fractal Properties
FRACTAL_PROPERTIES = {
    "self_similarity": "Patterns repeat across scales (micro → meso → macro)",
    "hypernode_nesting": "Hypernodes can contain other hypernodes (infinite depth)",
    "orp_repetition": "ORP structure repeats at every scale",
    "zoom_capability": "Can zoom in/out without losing coherence",
    "emergent_properties": "Macro properties emerge from micro interactions"
}

# Category Information
try:
    from app.kg.categories import (
        UPPER_ONTOLOGY, CATEGORIES,
        get_category_by_domain, get_upper_ontology_by_category, get_orp_role_by_category
    )
    CATEGORY_TAXONOMY_AVAILABLE = True
except ImportError:
    CATEGORY_TAXONOMY_AVAILABLE = False
    UPPER_ONTOLOGY = {}
    CATEGORIES = {}

# Schema Summary for LLM prompts
SCHEMA_SUMMARY = """
Knowledge Graph Schema (Fractal ORP Structure):

Node Types:
- Concept (C:uuid): Core knowledge unit with definitions, relations, operationalizations
- Claim (CL:uuid): Evidence-backed statements
- Evidence (E:uuid): Empirical or theoretical support
- Source (SRC:uuid): Academic papers, books, expert opinions
- Method (M:uuid): Research methodology
- Scope (S:uuid): Context and constraints
- Position (PO:uuid): Normative stances
- Hypernode (HN:uuid): Meta-node encapsulating subgraphs (enables fractal structure)
- Process (P:uuid): Dynamic flows/transformations in ORP model

Edge Types (Standard):
- DEFINES: Claim → Concept
- SUPPORTS/REFUTES: Evidence → Claim
- PREREQ/PrerequisiteOf: Concept → Concept (learning progression)
- PartOf: Concept → Concept (hierarchical)
- IsA: Concept → Concept (taxonomy)
- RELATED_TO: General relationships
- UNDER_SCOPE: Node → Scope
- CONTRADICTS: Claim ↔ Claim

Edge Types (Fractal ORP):
- CONTAINS: Hypernode → Node (hypernode contains subgraph)
- NESTED_IN: Node → Hypernode (node nested in hypernode)
- AGGREGATES: Hypernode → Node (aggregates properties)
- ENABLES: Process → Node (process enables transformation)
- INPUTS_TO: Node → Process (object/relation inputs to process)
- OUTPUTS_FROM: Process → Node (process outputs object/relation)
- SCALES_TO: Node → Node (fractal scaling: micro → meso → macro)
- MIRRORS: Node ↔ Node (self-similar patterns at different scales)

ORP Model (Object-Relation-Process):
- Objects: Building blocks (Concepts, Claims, Evidence)
- Relations: Connectors/enablers (edges between objects)
- Processes: Dynamic flows (Process nodes with inputs/outputs)
- Scales: micro (individual claims), meso (clusters), macro (domains)
- Fractal: ORP structure repeats at every scale

Fractal Properties:
- Self-similarity: Patterns repeat across scales
- Hypernode nesting: Infinite depth via nested hypernodes
- Zoom capability: Navigate micro → meso → macro seamlessly
- Emergent properties: Macro emerges from micro interactions

Category Structure:
- Upper Ontology (3): Entities (Objects), Relations, Events/Processes
- Categories (12): Mathematics, Natural Sciences, Engineering, Social Sciences, History, 
  Languages & Literature, Arts, Business & Economics, Health & Medicine, 
  Philosophy & Religion, Vocational, Interdisciplinary
- Domains (287): Organized under categories

Current KG State:
- 175 concepts
- 615 edges (3.51 per concept)
- 100% metadata and definition coverage

Validation:
- ≥2 independent supports per definition
- Completeness ≥80% for publishing
- PREREQ must be acyclic
- Hypernode containment must be acyclic
"""
