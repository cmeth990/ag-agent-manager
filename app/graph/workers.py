"""Worker nodes for LangGraph processing pipeline."""
import logging
import json
import uuid
from typing import Dict, Any
from app.graph.state import AgentState
from app.kg.diff import create_diff_id, create_empty_diff, format_diff_summary
from app.kg.provenance import enrich_diff_with_provenance
from app.security.prompt_injection import wrap_untrusted_content
from app.kg.knowledge_base import (
    NODE_TYPES, EDGE_TYPES, generate_id, validate_id, get_node_type_from_id,
    SCHEMA_SUMMARY, KG_STATE, ORP_SCALES, CATEGORY_TAXONOMY_AVAILABLE
)
from app.kg.hypernode import (
    detect_orp_pattern, infer_scale_from_content, create_orp_structure
)

# Import category functions if available
if CATEGORY_TAXONOMY_AVAILABLE:
    from app.kg.categories import (
        get_category_by_domain, get_upper_ontology_by_category, get_orp_role_by_category
    )
else:
    def get_category_by_domain(domain_name: str) -> str | None:
        return None
    def get_upper_ontology_by_category(category_key: str) -> str | None:
        return None
    def get_orp_role_by_category(category_key: str) -> str | None:
        return None
from app.llm.client import get_llm
from app.cost.cheap_verification import should_use_llm, simple_ner, statistical_extraction
from app.cost.cache import get_cache, cached
from app.llm.tiering import get_llm_for_task, TIER_CHEAP, TIER_MID
from app.validation.agent_outputs import (
    validate_extractor_output,
    validate_linker_output,
    validate_writer_output,
    validate_commit_output,
    validate_query_output,
    ValidationError as OutputValidationError,
)


logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """You are a knowledge graph extraction expert working with the Agnosia Knowledge Graph schema with FRACTAL ORP STRUCTURE.

KNOWLEDGE GRAPH SCHEMA (Fractal ORP):
Node Types (use as "label"):
- Concept: Core knowledge unit (e.g., "photosynthesis", "linear equations")
- Claim: Evidence-backed statements (e.g., "Photosynthesis converts CO2 to glucose")
- Evidence: Empirical or theoretical support
- Source: Academic papers, books, expert opinions
- Method: Research methodology
- Scope: Context and constraints
- Position: Normative stances
- Hypernode: Meta-node encapsulating subgraphs (enables fractal nesting)
- Process: Dynamic flows/transformations in ORP model

Edge Types (Standard):
- DEFINES: Claim → Concept (a claim defines a concept)
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
- ENABLES: Process → Node (process enables transformation)
- INPUTS_TO: Node → Process (object/relation inputs to process)
- OUTPUTS_FROM: Process → Node (process outputs object/relation)
- SCALES_TO: Node → Node (fractal scaling: micro → meso → macro)
- MIRRORS: Node ↔ Node (self-similar patterns at different scales)

ORP MODEL (Object-Relation-Process):
- Objects: Building blocks (Concepts, Claims, Evidence)
- Relations: Connectors (edges between objects)
- Processes: Dynamic flows (Process nodes with inputs/outputs)
- Scales: micro (individual claims), meso (clusters), macro (domains)
- Fractal: ORP structure repeats at every scale

FRACTAL EXTRACTION GUIDELINES:
1. **Detect Scale**: 
   - micro: Single concepts/claims (< 5 nodes)
   - meso: Clusters/subgraphs (5-20 nodes, e.g., "logic gate", "circuit module")
   - macro: Domains/hierarchies (> 20 nodes, e.g., "computational architecture")

2. **Identify ORP Patterns**:
   - Objects: Extract Concepts, Claims, Evidence as objects
   - Relations: Extract edges as relations
   - Processes: Identify dynamic flows (e.g., "signal propagation", "boolean evaluation", "recursive scaling")

3. **Hypernode Creation**:
   - If extracting a cluster/subgraph (meso/macro), create a Hypernode to encapsulate it
   - Use CONTAINS edges from hypernode to contained nodes
   - Set scale property: "micro", "meso", or "macro"

4. **Process Nodes**:
   - Extract dynamic transformations as Process nodes
   - Create INPUTS_TO edges from input objects to process
   - Create OUTPUTS_FROM edges from process to output objects
   - Set scale matching the ORP structure

5. **Fractal Scaling**:
   - If similar patterns exist at different scales, create SCALES_TO edges
   - If self-similar patterns detected, create MIRRORS edges

ID Format: Use prefixes C:, CL:, E:, SRC:, M:, S:, PO:, HN:, P: followed by UUID
For extraction, you can use temporary IDs like "C:temp_1" - they will be converted to proper UUIDs later.

Current KG State: 175 concepts, 615 edges, 100% metadata coverage

Extract:
1. **Entities**: Concepts, Claims, Evidence, Sources, Hypernodes, Processes
   - Each entity should have: id (with proper prefix), label (node type), properties (name, description, domain, scale, etc.)
   - **Provenance (required)**: Every Claim must link back to evidence. Either set properties.sourceId (Source id) or properties.evidenceIds (list of Evidence ids), or add SUPPORTS relations from Evidence nodes to the Claim.
2. **Relations**: Connections using proper edge types
   - Each relation should have: from (entity id), to (entity id), type (edge type), properties (optional)
3. **ORP Structure**: Identify objects, relations, and processes
   - If cluster detected, create Hypernode with CONTAINS edges
   - If processes detected, create Process nodes with INPUTS_TO/OUTPUTS_FROM edges

Return ONLY valid JSON in this exact format:
{{
  "entities": [
    {{"id": "C:temp_1", "label": "Concept", "properties": {{"name": "Photosynthesis", "domain": "biology", "description": "..."}}}},
    {{"id": "CL:temp_1", "label": "Claim", "properties": {{"text": "Photosynthesis converts CO2 to glucose", "claimType": "definition"}}}},
    {{"id": "HN:temp_1", "label": "Hypernode", "properties": {{"name": "Photosynthesis Cluster", "scale": "meso"}}}},
    {{"id": "P:temp_1", "label": "Process", "properties": {{"name": "CO2 Conversion", "processType": "transformation", "scale": "micro"}}}}
  ],
  "relations": [
    {{"from": "CL:temp_1", "to": "C:temp_1", "type": "DEFINES", "properties": {{"primary": true}}}},
    {{"from": "HN:temp_1", "to": "C:temp_1", "type": "CONTAINS", "properties": {{"containment_type": "orp_structure"}}}},
    {{"from": "C:temp_1", "to": "P:temp_1", "type": "INPUTS_TO", "properties": {{"scale": "micro"}}}}
  ],
  "claims": []
}}

If the input is a simple topic request like "topic=photosynthesis", extract:
- A Concept node for "photosynthesis"
- Optionally related concepts if mentioned
- PrerequisiteOf or PartOf relationships if learning progression is implied
- If multiple related concepts, consider creating a Hypernode to cluster them

User input: {user_input}

JSON:"""


async def extractor_node(state: AgentState) -> Dict[str, Any]:
    """
    Extract entities, relations, and claims from user input.
    Uses cheap verification first, only uses LLM if needed.
    
    Input: user_input
    Output: Extracted entities/relations in structured format
    """
    user_input = state.get("user_input", "")
    logger.info(f"Extracting from input: {user_input[:100]}...")
    
    # Cheap verification: check if we can extract without LLM
    use_llm, confidence, cheap_results = should_use_llm(user_input, confidence_threshold=0.7)
    
    # Check cache first
    cache = get_cache()
    cached_extraction = cache.get("extraction_result", user_input)
    
    if cached_extraction:
        logger.info("Using cached extraction result")
        extracted = cached_extraction
    elif not use_llm:
        # Cheap extraction sufficient
        logger.info(f"Using cheap extraction (confidence: {confidence:.2f})")
        # Build simple extraction from NER and statistics
        ner = cheap_results.get("ner", {})
        stats = cheap_results.get("statistics", {})
        
        # Extract topic name
        topic_name = user_input.split("=")[-1].strip() if "=" in user_input else user_input
        if ner.get("proper_nouns"):
            topic_name = ner["proper_nouns"][0] if ner["proper_nouns"] else topic_name
        
        extracted = {
            "entities": [
                {
                    "id": generate_id("Concept"),
                    "label": "Concept",
                    "properties": {
                        "name": topic_name,
                        "description": f"Topic: {topic_name}",
                        "domain": "general",
                        "extraction_method": "cheap_verification",
                        "confidence": confidence,
                    }
                }
            ],
            "relations": [],
            "claims": []
        }
        
        # Structured output validation (guardrails)
        try:
            extracted = validate_extractor_output(extracted)
        except OutputValidationError as ve:
            logger.warning(f"Extractor output validation: {ve}; using as-is with truncation")
        cache.set("extraction_result", extracted, ttl_seconds=86400, user_input=user_input)
    else:
        # LLM extraction needed
        logger.info(f"Using LLM extraction (confidence: {confidence:.2f})")
        
        # Use tiered model: extraction is mid-tier task
        llm = get_llm_for_task("extraction", domain=None, queue=None, agent="extractor")
        if not llm:
            llm = get_llm()  # Fallback to base LLM
        
        if not llm:
            # Fallback to simple extraction if no LLM available
            logger.warning("No LLM available, using fallback extraction")
            topic_name = user_input.split("=")[-1].strip() if "=" in user_input else user_input
            extracted = {
                "entities": [
                    {
                        "id": f"entity_{uuid.uuid4().hex[:8]}",
                        "label": "Topic",
                        "properties": {"name": topic_name, "description": f"Topic: {topic_name}"}
                    }
                ],
                "relations": [],
                "claims": []
            }
        else:
            try:
                # Prompt injection defense: treat user input as untrusted data
                safe_input = wrap_untrusted_content(user_input, max_length=20_000)
                prompt = EXTRACTION_PROMPT.format(user_input=safe_input)
                response = await llm.ainvoke(prompt)
                
                # Parse JSON response
                content = response.content.strip()
                # Remove markdown code blocks if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                extracted = json.loads(content)
                
                # Cache LLM extraction result
                cache = get_cache()
                cache.set("extraction_result", extracted, ttl_seconds=86400, user_input=user_input)
                
                # Ensure all entities have proper IDs with prefixes
                for i, entity in enumerate(extracted.get("entities", [])):
                    if "id" not in entity:
                        label = entity.get("label", "Concept")
                        # Map common labels to node types
                        label_map = {
                            "Person": "Concept",
                            "Topic": "Concept",
                            "Entity": "Concept"
                        }
                        node_type = label_map.get(label, label)
                        if node_type in NODE_TYPES:
                            entity["id"] = generate_id(node_type)
                        else:
                            # Default to Concept if unknown
                            entity["id"] = generate_id("Concept")
                    # Validate and fix ID format if needed
                    elif not validate_id(entity["id"]):
                        # If ID doesn't match format, generate new one
                        label = entity.get("label", "Concept")
                        label_map = {"Person": "Concept", "Topic": "Concept", "Entity": "Concept"}
                        node_type = label_map.get(label, label)
                        if node_type not in NODE_TYPES:
                            node_type = "Concept"
                        entity["id"] = generate_id(node_type)
                
                logger.info(f"Extracted {len(extracted.get('entities', []))} entities, {len(extracted.get('relations', []))} relations")
                # Structured output validation (guardrails)
                try:
                    extracted = validate_extractor_output(extracted)
                except OutputValidationError as ve:
                    logger.warning(f"Extractor output validation: {ve}; using as-is")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Response content: {response.content if 'response' in locals() else 'N/A'}")
                # Fallback extraction with proper KG ID format
                topic_name = user_input.split("=")[-1].strip() if "=" in user_input else user_input
                extracted = {
                    "entities": [
                        {
                            "id": generate_id("Concept"),
                            "label": "Concept",
                            "properties": {"name": topic_name, "description": f"Topic: {topic_name}", "domain": "general"}
                        }
                    ],
                    "relations": [],
                    "claims": []
                }
            except Exception as e:
                logger.error(f"Error in LLM extraction: {e}", exc_info=True)
                # Fallback extraction with proper KG ID format
                topic_name = user_input.split("=")[-1].strip() if "=" in user_input else user_input
                extracted = {
                    "entities": [
                        {
                            "id": generate_id("Concept"),
                            "label": "Concept",
                            "properties": {"name": topic_name, "description": f"Topic: {topic_name}", "domain": "general"}
                        }
                    ],
                    "relations": [],
                    "claims": []
                }
    
    return {
        "working_notes": {
            **state.get("working_notes", {}),
            "extracted": extracted
        }
    }


# Helper functions
def normalize_name(name: str) -> str:
    """Normalize entity name for matching."""
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def map_label_to_node_type(label: str) -> str:
    """Map entity label to proper KG node type."""
    label_map = {
        "Person": "Concept",
        "Topic": "Concept",
        "Entity": "Concept",
        "Concept": "Concept",
        "Claim": "Claim",
        "Evidence": "Evidence",
        "Source": "Source",
        "Method": "Method",
        "Scope": "Scope",
        "Position": "Position"
    }
    return label_map.get(label, "Concept")


async def linker_node(state: AgentState) -> Dict[str, Any]:
    """
    Deduplicate and link entities to canonical IDs.
    
    Input: working_notes.extracted
    Output: Linked entities with canonical IDs
    
    Performs basic entity linking:
    - Normalizes entity names for matching
    - Checks for existing entities in KG (if available)
    - Maps to canonical IDs
    """
    working_notes = state.get("working_notes", {})
    extracted = working_notes.get("extracted", {})
    entities = extracted.get("entities", [])
    relations = extracted.get("relations", [])
    
    logger.info(f"Linking {len(entities)} entities")
    
    # Build canonical ID mapping
    canonical_ids = {}
    linked_entities = []
    entity_name_map = {}  # normalized_name -> canonical_id
    
    # Try to query KG for existing entities (if KG client available)
    kg_entities = {}
    try:
        from app.kg.client import query_entities
        entity_names = [e.get("properties", {}).get("name", "") for e in entities if e.get("properties", {}).get("name")]
        if entity_names:
            kg_entities = await query_entities(entity_names)
            logger.info(f"Found {len(kg_entities)} existing entities in KG")
    except Exception as e:
        logger.debug(f"Could not query KG for existing entities: {e}")
    
    # Process each entity
    for entity in entities:
        entity_id = entity.get("id", "")
        entity_label = entity.get("label", "Concept")
        entity_name = entity.get("properties", {}).get("name", "")
        normalized_name = normalize_name(entity_name) if entity_name else None
        
        # Ensure entity has proper ID format
        if not entity_id or not validate_id(entity_id):
            node_type = map_label_to_node_type(entity_label)
            entity_id = generate_id(node_type)
            entity["id"] = entity_id
        
        # Check if entity exists in KG
        canonical_id = None
        if normalized_name and normalized_name in kg_entities:
            # Use existing KG entity ID
            canonical_id = kg_entities[normalized_name]
            canonical_ids[entity_id] = canonical_id
            logger.debug(f"Linked {entity_name} to existing KG entity {canonical_id}")
        elif normalized_name and normalized_name in entity_name_map:
            # Use canonical ID from already processed entities in this batch
            canonical_id = entity_name_map[normalized_name]
            canonical_ids[entity_id] = canonical_id
            logger.debug(f"Linked {entity_name} to canonical ID {canonical_id} (deduplicated)")
        else:
            # New entity - use its ID as canonical
            canonical_id = entity_id
            canonical_ids[entity_id] = canonical_id
            if normalized_name:
                entity_name_map[normalized_name] = canonical_id
        
        # Add to linked entities (use canonical ID)
        linked_entity = entity.copy()
        linked_entity["id"] = canonical_id
        # Ensure label matches KG node type
        node_type = get_node_type_from_id(canonical_id)
        if node_type:
            linked_entity["label"] = node_type
        linked_entities.append(linked_entity)
    
    # Update relation references to use canonical IDs
    linked_relations = []
    for rel in relations:
        from_id = rel.get("from")
        to_id = rel.get("to")
        
        # Map to canonical IDs
        canonical_from = canonical_ids.get(from_id, from_id)
        canonical_to = canonical_ids.get(to_id, to_id)
        
        linked_rel = rel.copy()
        linked_rel["from"] = canonical_from
        linked_rel["to"] = canonical_to
        linked_relations.append(linked_rel)
    
    linked = {
        "entities": linked_entities,
        "relations": linked_relations,
        "canonical_ids": canonical_ids
    }
    # Structured output validation (guardrails)
    try:
        linked = validate_linker_output(linked)
    except OutputValidationError as ve:
        logger.warning(f"Linker output validation: {ve}; using as-is")
    
    logger.info(f"Linked to {len(set(canonical_ids.values()))} unique entities")
    
    return {
        "working_notes": {
            **working_notes,
            "linked": linked
        }
    }


def writer_node(state: AgentState) -> Dict[str, Any]:
    """
    Produce proposed_diff from linked entities.
    
    Input: working_notes.linked
    Output: proposed_diff, approval_required=True
    
    This creates a diff structure but does NOT commit it.
    """
    working_notes = state.get("working_notes", {})
    linked = working_notes.get("linked", {})
    logger.info("Generating proposed diff")
    
    # Create diff structure
    diff = create_empty_diff()
    diff_id = create_diff_id()
    
    # Convert linked entities to diff format
    entities = linked.get("entities", [])
    
    # Detect ORP patterns and create hypernodes if needed
    orp_pattern = detect_orp_pattern(entities, linked.get("relations", []))
    
    # If we have a cluster (meso/macro scale), create hypernode
    should_create_hypernode = (
        len(entities) >= 5 or  # 5+ nodes suggests cluster
        any(e.get("label") == "Hypernode" for e in entities) or
        any("cluster" in str(e.get("properties", {}).get("name", "")).lower() for e in entities)
    )
    
    hypernode_id = None
    if should_create_hypernode and not any(e.get("label") == "Hypernode" for e in entities):
        # Infer scale from content
        content = state.get("user_input", "")
        scale = infer_scale_from_content(content, len(entities))
        
        # Create hypernode
        from app.kg.hypernode import create_hypernode
        hypernode = create_hypernode(
            name=f"Cluster_{len(entities)}_nodes",
            scale=scale,
            subgraph_nodes=[e.get("id") for e in entities if e.get("id")],
            orp_structure={
                "objects": [e["id"] for e in orp_pattern.get("objects", [])],
                "relations": [],
                "processes": [e["id"] for e in entities if e.get("label") == "Process"]
            }
        )
        hypernode_id = hypernode["id"]
        diff["nodes"]["add"].append(hypernode)
    
    for entity in entities:
        entity_id = entity.get("id", "unknown")
        entity_label = entity.get("label", "Concept")
        
        # Map label to proper KG node type
        node_type = map_label_to_node_type(entity_label)
        if validate_id(entity_id):
            # Get node type from ID if valid
            id_node_type = get_node_type_from_id(entity_id)
            if id_node_type:
                node_type = id_node_type
        
        # Include entity ID in properties for Neo4j matching
        properties = entity.get("properties", {}).copy()
        properties["id"] = entity_id  # Store original ID
        
        # Add scale property if not present (for ORP)
        if "scale" not in properties and node_type in ["Concept", "Claim", "Process", "Hypernode"]:
            content = state.get("user_input", "")
            properties["scale"] = infer_scale_from_content(content, len(entities))
        
        # Add category information if domain is present
        if node_type == "Concept" and "domain" in properties:
            domain_name = properties["domain"]
            category_key = get_category_by_domain(domain_name)
            if category_key:
                properties["category"] = category_key
                upper_ontology = get_upper_ontology_by_category(category_key)
                orp_role = get_orp_role_by_category(category_key)
                if upper_ontology:
                    properties["upper_ontology"] = upper_ontology
                if orp_role:
                    properties["orp_role"] = orp_role
        
        diff["nodes"]["add"].append({
            "id": entity_id,
            "label": node_type,  # Use proper KG node type
            "properties": properties
        })
        
        # If hypernode created, add CONTAINS edge
        if hypernode_id and node_type != "Hypernode":
            diff["edges"]["add"].append({
                "from": hypernode_id,
                "to": entity_id,
                "type": "CONTAINS",
                "properties": {
                    "containment_type": "orp_structure",
                    "compression_level": 0.5
                }
            })
    
    relations = linked.get("relations", [])
    for rel in relations:
        edge_type = rel.get("type", "RELATED_TO")
        # Validate edge type against known types
        if edge_type not in EDGE_TYPES:
            # Try to map common edge types
            edge_type_map = {
                "STUDIES": "RELATED_TO",
                "WORKS_ON": "RELATED_TO",
                "KNOWS": "RELATED_TO",
                "PREREQ": "PrerequisiteOf",
                "PREREQUISITE": "PrerequisiteOf"
            }
            edge_type = edge_type_map.get(edge_type, "RELATED_TO")
            logger.debug(f"Mapped edge type {rel.get('type')} to {edge_type}")
        
        diff["edges"]["add"].append({
            "from": rel.get("from"),
            "to": rel.get("to"),
            "type": edge_type,
            "properties": rel.get("properties", {})
        })
    
    diff["metadata"]["source"] = state.get("user_input")
    diff["metadata"]["reason"] = f"User requested: {state.get('intent', 'unknown')}"
    enrich_diff_with_provenance(
        diff,
        source_agent="writer_node",
        source_document=state.get("user_input"),
        reasoning=f"Extraction from user input; intent: {state.get('intent', 'unknown')}",
    )
    logger.info(f"Generated diff {diff_id}: {format_diff_summary(diff)}")
    out = {
        "proposed_diff": diff,
        "diff_id": diff_id,
        "approval_required": True,
        "crucial_decision_type": "kg_write",
        "final_response": f"📝 Proposed KG changes:\n\n{format_diff_summary(diff)}\n\nPlease review and approve or reject."
    }
    try:
        validate_writer_output(out)
    except OutputValidationError as ve:
        logger.warning(f"Writer output validation: {ve}")
    return out


async def commit_node(state: AgentState) -> Dict[str, Any]:
    """
    Commit diff to KG if approved, or handle rejection.
    
    Input: proposed_diff, approval_decision
    Output: final_response with commit results
    """
    approval_decision = state.get("approval_decision")
    proposed_diff = state.get("proposed_diff")
    
    if approval_decision == "reject":
        logger.info("Diff rejected by user")
        return {
            "proposed_diff": None,
            "approval_required": False,
            "crucial_decision_type": None,
            "crucial_decision_context": None,
            "final_response": "❌ Changes rejected. Please provide clarification or a new command."
        }
    
    if approval_decision != "approve":
        logger.warning(f"Unexpected approval_decision: {approval_decision}")
        return {
            "error": f"Invalid approval decision: {approval_decision}"
        }
    
    if not proposed_diff:
        return {
            "error": "No proposed diff to commit"
        }
    
    # Import here to avoid circular dependency
    from app.kg.client import apply_diff
    
    logger.info("Committing diff to KG")
    result = await apply_diff(proposed_diff)
    
    if result.get("success"):
        summary = format_diff_summary(proposed_diff)
        response = f"✅ Committed to KG:\n\n{summary}\n\n"
        response += f"Nodes: +{result['nodes']['added']} ~{result['nodes']['updated']} -{result['nodes']['deleted']}\n"
        response += f"Edges: +{result['edges']['added']} ~{result['edges']['updated']} -{result['edges']['deleted']}"
        out = {
            "proposed_diff": None,
            "approval_required": False,
            "crucial_decision_type": None,
            "crucial_decision_context": None,
            "final_response": response
        }
    else:
        out = {
            "error": "Failed to commit diff",
            "final_response": "❌ Error committing changes. Please try again."
        }
    try:
        validate_commit_output(out)
    except OutputValidationError as ve:
        logger.warning(f"Commit output validation: {ve}")
    return out


def handle_reject_node(state: AgentState) -> Dict[str, Any]:
    """Handle rejection - clear diff and request clarification."""
    logger.info("Handling rejection")
    return {
        "proposed_diff": None,
        "approval_required": False,
        "crucial_decision_type": None,
        "crucial_decision_context": None,
        "final_response": "❌ Changes rejected. What would you like to do instead?"
    }


async def query_node(state: AgentState) -> Dict[str, Any]:
    """
    Query the knowledge graph based on user input.
    Supports fractal navigation: expand, zoom, scale queries.
    
    Input: user_input (query text)
    Output: final_response with query results
    """
    user_input = state.get("user_input", "")
    logger.info(f"Querying KG: {user_input[:100]}...")
    
    # Extract query from user input (remove /query prefix if present)
    query_text = user_input.replace("/query", "").strip()
    if not query_text:
        return {
            "final_response": "❌ Please provide a query. Example: /query What is photosynthesis?"
        }
    
    try:
        from app.kg.client import query_kg, expand_hypernode, query_fractal_scale, query_orp_structure
        
        # Check for fractal navigation commands
        query_lower = query_text.lower()
        
        # Expand hypernode
        if query_lower.startswith("expand ") or query_lower.startswith("zoom in "):
            hypernode_id = query_text.split(" ", 1)[-1].strip()
            expansion = await expand_hypernode(hypernode_id)
            if expansion.get("nodes"):
                response = f"🔍 Expanded Hypernode {hypernode_id}:\n\n"
                response += f"Nodes: {len(expansion['nodes'])}\n"
                response += f"Edges: {len(expansion['edges'])}\n\n"
                for i, node in enumerate(expansion["nodes"][:10], 1):
                    name = node.get("properties", {}).get("name", node.get("id", "Unknown"))
                    response += f"{i}. {name} ({node.get('label', 'Unknown')})\n"
                return {"final_response": response}
            else:
                return {"final_response": f"❌ Could not expand hypernode {hypernode_id}"}
        
        # Query fractal scale
        if query_lower.startswith("scale to ") or query_lower.startswith("zoom to "):
            parts = query_text.split(" ", 2)
            if len(parts) >= 3:
                node_id = parts[1]
                target_scale = parts[2].lower()
                if target_scale in ["micro", "meso", "macro"]:
                    scale_results = await query_fractal_scale(node_id, target_scale)
                    response = f"🔍 Fractal Scale Query: {node_id} → {target_scale}\n\n"
                    response += f"Found {len(scale_results.get('nodes', []))} nodes at {target_scale} scale\n"
                    for i, node in enumerate(scale_results.get("nodes", [])[:10], 1):
                        name = node.get("properties", {}).get("name", node.get("id", "Unknown"))
                        response += f"{i}. {name}\n"
                    return {"final_response": response}
        
        # Query ORP structure
        if query_lower.startswith("orp ") or query_lower.startswith("structure "):
            node_id = query_text.split(" ", 1)[-1].strip()
            orp = await query_orp_structure(node_id)
            response = f"🔍 ORP Structure for {node_id}:\n\n"
            response += f"Objects: {len(orp.get('objects', []))}\n"
            response += f"Processes: {len(orp.get('processes', []))}\n"
            response += f"Relations: {len(orp.get('relations', []))}\n"
            return {"final_response": response}
        
        # Standard query
        results = await query_kg(query_text)
        
        if not results:
            return {
                "final_response": f"🔍 No results found for: {query_text}\n\nTry a different query or add knowledge first with /ingest\n\nFractal commands:\n- /query expand <hypernode_id>\n- /query scale to <node_id> <micro|meso|macro>\n- /query orp <node_id>"
            }
        
        # Format results
        response = f"🔍 Query: {query_text}\n\n"
        response += f"Found {len(results)} result(s):\n\n"
        
        for i, result in enumerate(results[:10], 1):  # Limit to 10 results
            if isinstance(result, dict):
                if "name" in result:
                    response += f"{i}. {result['name']}"
                    if "description" in result:
                        response += f" - {result['description'][:100]}"
                    # Show scale if available
                    props = result.get("properties", {})
                    if "scale" in props:
                        response += f" [{props['scale']}]"
                    response += "\n"
                elif "type" in result:
                    response += f"{i}. {result.get('type', 'Unknown')} relation"
                    if "from" in result and "to" in result:
                        response += f": {result['from']} -> {result['to']}"
                    response += "\n"
                else:
                    response += f"{i}. {str(result)[:100]}\n"
            else:
                response += f"{i}. {str(result)[:100]}\n"
        
        if len(results) > 10:
            response += f"\n... and {len(results) - 10} more results"
        
        response += "\n\n💡 Fractal Navigation:\n"
        response += "- /query expand <hypernode_id> - Expand hypernode\n"
        response += "- /query scale to <node_id> <micro|meso|macro> - Query fractal scale\n"
        response += "- /query orp <node_id> - View ORP structure\n"
        
        out = {"final_response": response}
        try:
            validate_query_output(out)
        except OutputValidationError as ve:
            logger.warning(f"Query output validation: {ve}")
        return out
    
    except Exception as e:
        logger.error(f"Error querying KG: {e}", exc_info=True)
        return {
            "error": str(e),
            "final_response": f"❌ Error querying knowledge graph: {e}"
        }
