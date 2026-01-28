"""
Agent output validation schemas and validators.
Ensures every agent output can be validated by code before processing.
If you do only one thing: force structured outputs and validate them in code.
"""
import logging
import os
from typing import Dict, Any, List, Optional

from app.validation.schemas import (
    get_node_type_allowlist,
    get_edge_type_allowlist,
    CLAIM_TYPE_ALLOWLIST,
    Thresholds,
    PROVENANCE_REQUIRED_FOR_LABELS,
    STATE_UPDATE_ALLOWLIST,
    INTENT_ALLOWLIST,
    APPROVAL_DECISION_ALLOWLIST,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when agent output fails validation."""
    pass


def _validate_string(value: Any, field: str, max_len: int = 50000) -> str:
    """Ensure value is a non-empty string within length limit."""
    if value is None:
        raise ValidationError(f"{field} must not be None")
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be str, got {type(value).__name__}")
    s = value.strip()
    if len(s) > max_len:
        raise ValidationError(f"{field} exceeds max length {max_len}")
    return s


def _validate_list_of_strings(value: Any, field: str, max_items: int = 1000) -> List[str]:
    """Ensure value is a list of strings."""
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be list, got {type(value).__name__}")
    if len(value) > max_items:
        raise ValidationError(f"{field} has too many items (max {max_items})")
    out = []
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValidationError(f"{field}[{i}] must be str, got {type(item).__name__}")
        out.append(str(item).strip())
    return out


def _validate_source_item(source: Any, index: int) -> Dict[str, Any]:
    """Validate a single source dict from source gatherer."""
    if not isinstance(source, dict):
        raise ValidationError(f"source[{index}] must be dict, got {type(source).__name__}")
    props = source.get("properties") or {}
    if not isinstance(props, dict):
        raise ValidationError(f"source[{index}].properties must be dict")
    # Required for downstream use
    if "title" not in props and "name" not in props:
        raise ValidationError(f"source[{index}] must have properties.title or properties.name")
    # Ensure numeric scores are valid
    for key in ("quality_score", "cost_score", "priority_score"):
        if key in source:
            v = source[key]
            if v is not None and not isinstance(v, (int, float)):
                try:
                    source[key] = float(v)
                except (TypeError, ValueError):
                    raise ValidationError(f"source[{index}].{key} must be numeric")
    return source


def validate_source_gatherer_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate source gatherer node output.
    Returns sanitized output; raises ValidationError on failure.
    """
    if not isinstance(output, dict):
        raise ValidationError("Source gatherer output must be dict")
    validated = {}
    if "final_response" in output and output["final_response"] is not None:
        validated["final_response"] = _validate_string(
            output["final_response"], "final_response", max_len=50000
        )
    if "discovered_sources" in output and output["discovered_sources"] is not None:
        ds = output["discovered_sources"]
        if not isinstance(ds, dict):
            raise ValidationError("discovered_sources must be dict")
        validated["discovered_sources"] = {"domains": [], "sources_by_domain": {}, "all_sources": []}
        if "domains" in ds:
            validated["discovered_sources"]["domains"] = _validate_list_of_strings(
                ds["domains"], "discovered_sources.domains", max_items=50
            )
        if "all_sources" in ds and isinstance(ds["all_sources"], list):
            validated["discovered_sources"]["all_sources"] = [
                _validate_source_item(s, i) for i, s in enumerate(ds["all_sources"][:200])
            ]
        if "sources_by_domain" in ds and isinstance(ds["sources_by_domain"], dict):
            validated["discovered_sources"]["sources_by_domain"] = ds["sources_by_domain"]
    if "error" in output and output["error"]:
        validated["error"] = _validate_string(str(output["error"]), "error", max_len=1000)
    return validated if validated else output


def validate_domain_scout_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate domain scout node output.
    """
    if not isinstance(output, dict):
        raise ValidationError("Domain scout output must be dict")
    validated = {}
    if "final_response" in output and output["final_response"] is not None:
        validated["final_response"] = _validate_string(
            output["final_response"], "final_response", max_len=50000
        )
    if "scouting_results" in output and output["scouting_results"] is not None:
        sr = output["scouting_results"]
        if not isinstance(sr, dict):
            raise ValidationError("scouting_results must be dict")
        validated["scouting_results"] = {
            k: v for k, v in sr.items()
            if isinstance(v, (dict, list, str, int, float, bool)) or v is None
        }
    if "error" in output and output["error"]:
        validated["error"] = _validate_string(str(output["error"]), "error", max_len=1000)
    return validated if validated else output


def validate_improvement_agent_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate improvement agent output (proposed changes, plan).
    """
    if not isinstance(output, dict):
        raise ValidationError("Improvement agent output must be dict")
    validated = dict(output)
    if "proposed_changes" in output and output["proposed_changes"]:
        pc = output["proposed_changes"]
        if not isinstance(pc, dict):
            raise ValidationError("proposed_changes must be dict")
        for path, content in pc.items():
            if not isinstance(path, str) or not path.endswith(".py"):
                raise ValidationError(f"proposed_changes key must be .py path: {path}")
            if not isinstance(content, str):
                raise ValidationError(f"proposed_changes[{path}] must be str")
            if len(content) > 500_000:
                raise ValidationError(f"proposed_changes[{path}] exceeds max size")
    if "improvement_plan" in output and output["improvement_plan"]:
        plan = output["improvement_plan"]
        if not isinstance(plan, dict):
            raise ValidationError("improvement_plan must be dict")
        if "files_to_modify" in plan and not isinstance(plan["files_to_modify"], list):
            raise ValidationError("improvement_plan.files_to_modify must be list")
    if "final_response" in output and output["final_response"]:
        validated["final_response"] = _validate_string(
            output["final_response"], "final_response", max_len=50000
        )
    if "error" in output and output["error"]:
        validated["error"] = _validate_string(str(output["error"]), "error", max_len=1000)
    return validated


def _validate_entity_for_extraction(entity: Any, index: int, node_allowlist: frozenset, edge_allowlist: frozenset) -> Dict[str, Any]:
    """Validate a single entity from extractor output; enforce allowlists."""
    if not isinstance(entity, dict):
        raise ValidationError(f"entities[{index}] must be dict, got {type(entity).__name__}")
    eid = entity.get("id")
    label = entity.get("label")
    props = entity.get("properties")
    if not isinstance(props, dict):
        raise ValidationError(f"entities[{index}].properties must be dict")
    if label and node_allowlist and label not in node_allowlist:
        raise ValidationError(f"entities[{index}].label '{label}' not in allowlist")
    if eid and isinstance(eid, str) and len(eid) > 200:
        raise ValidationError(f"entities[{index}].id exceeds max length")
    for k, v in (props or {}).items():
        if isinstance(v, str) and len(v) > Thresholds.MAX_PROPERTY_VALUE_LENGTH:
            raise ValidationError(f"entities[{index}].properties.{k} exceeds max length")
    if props and len(props) > Thresholds.MAX_ENTITY_PROPERTIES:
        raise ValidationError(f"entities[{index}].properties has too many keys")
    return entity


def _validate_relation_for_extraction(rel: Any, index: int, edge_allowlist: frozenset) -> Dict[str, Any]:
    """Validate a single relation from extractor output."""
    if not isinstance(rel, dict):
        raise ValidationError(f"relations[{index}] must be dict, got {type(rel).__name__}")
    if not rel.get("from") or not rel.get("to") or not rel.get("type"):
        raise ValidationError(f"relations[{index}] must have from, to, type")
    if edge_allowlist and rel.get("type") not in edge_allowlist:
        raise ValidationError(f"relations[{index}].type '{rel.get('type')}' not in allowlist")
    return rel


def validate_extractor_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate extractor node output (working_notes.extracted).
    Enforces: structured entities/relations, allowlists, thresholds, provenance hints.
    """
    if not isinstance(output, dict):
        raise ValidationError("Extractor output must be dict")
    entities = output.get("entities", [])
    relations = output.get("relations", [])
    claims = output.get("claims", [])
    if not isinstance(entities, list):
        raise ValidationError("entities must be list")
    if not isinstance(relations, list):
        raise ValidationError("relations must be list")
    if not isinstance(claims, list):
        raise ValidationError("claims must be list")
    if len(entities) > Thresholds.MAX_ENTITIES_PER_EXTRACTION:
        raise ValidationError(f"entities count exceeds max ({Thresholds.MAX_ENTITIES_PER_EXTRACTION})")
    if len(relations) > Thresholds.MAX_RELATIONS_PER_EXTRACTION:
        raise ValidationError(f"relations count exceeds max ({Thresholds.MAX_RELATIONS_PER_EXTRACTION})")
    if len(claims) > Thresholds.MAX_CLAIMS_PER_EXTRACTION:
        raise ValidationError(f"claims count exceeds max ({Thresholds.MAX_CLAIMS_PER_EXTRACTION})")

    node_allowlist = get_node_type_allowlist()
    edge_allowlist = get_edge_type_allowlist()
    validated_entities = [_validate_entity_for_extraction(e, i, node_allowlist, edge_allowlist) for i, e in enumerate(entities)]
    validated_relations = [_validate_relation_for_extraction(r, i, edge_allowlist) for i, r in enumerate(relations)]

    # Provenance: Claims should have sourceId or evidence refs
    require_provenance = os.getenv("REQUIRE_CLAIM_PROVENANCE", "false").lower() == "true"
    claim_ids_without_provenance = set()
    
    for i, entity in enumerate(validated_entities):
        if entity.get("label") == "Claim":
            props = entity.get("properties") or {}
            has_provenance = (
                props.get("sourceId") or props.get("evidenceIds") or
                any(r.get("type") == "SUPPORTS" and r.get("to") == entity.get("id") for r in validated_relations)
            )
            if not has_provenance:
                if require_provenance:
                    claim_ids_without_provenance.add(entity.get("id"))
                    logger.warning(f"Provenance: Claim entities[{i}] (id={entity.get('id')}) has no sourceId/evidenceIds; will be filtered out")
                else:
                    logger.debug(f"Provenance: Claim entities[{i}] has no sourceId/evidenceIds; consider adding evidence link")
    
    if require_provenance and claim_ids_without_provenance:
        # Quarantine: filter out Claims without provenance and relations referencing them
        validated_entities = [e for e in validated_entities if e.get("id") not in claim_ids_without_provenance]
        validated_relations = [
            r for r in validated_relations
            if r.get("from") not in claim_ids_without_provenance and r.get("to") not in claim_ids_without_provenance
        ]
        logger.info(f"Filtered {len(claim_ids_without_provenance)} Claim(s) without provenance (REQUIRE_CLAIM_PROVENANCE=true)")
    
    return {
        "entities": validated_entities,
        "relations": validated_relations,
        "claims": claims if isinstance(claims, list) else [],
    }


def validate_linker_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate linker node output (working_notes.linked).
    Enforces: entities/relations/canonical_ids structure, thresholds.
    """
    if not isinstance(output, dict):
        raise ValidationError("Linker output must be dict")
    entities = output.get("entities", [])
    relations = output.get("relations", [])
    canonical_ids = output.get("canonical_ids", {})
    if not isinstance(entities, list):
        raise ValidationError("linked.entities must be list")
    if not isinstance(relations, list):
        raise ValidationError("linked.relations must be list")
    if not isinstance(canonical_ids, dict):
        raise ValidationError("linked.canonical_ids must be dict")
    if len(entities) > Thresholds.MAX_LINKED_ENTITIES:
        raise ValidationError(f"linked entities count exceeds max ({Thresholds.MAX_LINKED_ENTITIES})")
    if len(relations) > Thresholds.MAX_LINKED_RELATIONS:
        raise ValidationError(f"linked relations count exceeds max ({Thresholds.MAX_LINKED_RELATIONS})")
    return output


def validate_content_fetcher_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Validate content fetcher LLM parsed JSON (domains, max_sources, min_priority)."""
    if not isinstance(parsed, dict):
        raise ValidationError("Content fetcher parsed output must be dict")
    domains = parsed.get("domains", [])
    if not isinstance(domains, list):
        raise ValidationError("domains must be list")
    domains = [str(d).strip() for d in domains if d][:Thresholds.MAX_DOMAINS_PER_REQUEST]
    max_sources = parsed.get("max_sources", 10)
    if isinstance(max_sources, (int, float)):
        max_sources = max(1, min(int(max_sources), Thresholds.MAX_SOURCES_PER_DOMAIN))
    else:
        max_sources = 10
    min_priority = parsed.get("min_priority", 0.0)
    if isinstance(min_priority, (int, float)):
        min_priority = max(0.0, min(1.0, float(min_priority)))
    else:
        min_priority = 0.0
    return {"domains": domains, "max_sources": max_sources, "min_priority": min_priority}


def validate_commit_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Validate commit node output (state update keys and types)."""
    if not isinstance(output, dict):
        raise ValidationError("Commit output must be dict")
    for k in output:
        if k not in STATE_UPDATE_ALLOWLIST:
            raise ValidationError(f"Commit output key '{k}' not in state allowlist")
    if "approval_decision" in output and output.get("approval_decision") is not None:
        if output["approval_decision"] not in APPROVAL_DECISION_ALLOWLIST:
            raise ValidationError(f"approval_decision must be in {set(APPROVAL_DECISION_ALLOWLIST)}")
    if "final_response" in output and output.get("final_response") is not None:
        _validate_string(str(output["final_response"]), "final_response", max_len=Thresholds.MAX_QUERY_RESPONSE_LENGTH)
    return output


def validate_query_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Validate query node output (final_response length, allowed keys)."""
    if not isinstance(output, dict):
        raise ValidationError("Query output must be dict")
    for k in output:
        if k not in STATE_UPDATE_ALLOWLIST:
            raise ValidationError(f"Query output key '{k}' not in state allowlist")
    if "final_response" in output and output.get("final_response") is not None:
        _validate_string(str(output["final_response"]), "final_response", max_len=Thresholds.MAX_QUERY_RESPONSE_LENGTH)
    return output


def validate_writer_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Validate writer node output (proposed_diff structure and thresholds)."""
    if not isinstance(output, dict):
        raise ValidationError("Writer output must be dict")
    diff = output.get("proposed_diff")
    if diff is not None and isinstance(diff, dict):
        nodes = diff.get("nodes", {})
        edges = diff.get("edges", {})
        for key, max_val in [
            ("add", Thresholds.MAX_NODES_ADD),
            ("update", Thresholds.MAX_NODES_UPDATE),
            ("delete", Thresholds.MAX_NODES_DELETE),
        ]:
            lst = nodes.get(key, [])
            if isinstance(lst, list) and len(lst) > max_val:
                raise ValidationError(f"proposed_diff.nodes.{key} exceeds max ({max_val})")
        for key, max_val in [
            ("add", Thresholds.MAX_EDGES_ADD),
            ("update", Thresholds.MAX_EDGES_UPDATE),
            ("delete", Thresholds.MAX_EDGES_DELETE),
        ]:
            lst = edges.get(key, [])
            if isinstance(lst, list) and len(lst) > max_val:
                raise ValidationError(f"proposed_diff.edges.{key} exceeds max ({max_val})")
    return output


def validate_agent_state_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a state update that will be merged into AgentState.
    Ensures types are safe and within bounds; only allowed keys.
    """
    if not isinstance(update, dict):
        raise ValidationError("State update must be dict")
    validated = {}
    for k, v in update.items():
        if k not in STATE_UPDATE_ALLOWLIST:
            logger.warning(f"State update contains unknown key: {k}")
            continue
        if k == "final_response" and v is not None:
            validated[k] = _validate_string(str(v), k, max_len=50000)
        elif k == "error" and v is not None:
            validated[k] = _validate_string(str(v), k, max_len=2000)
        elif k == "user_input" and v is not None:
            validated[k] = _validate_string(str(v), k, max_len=10000)
        elif k == "chat_id":
            validated[k] = str(v) if v is not None else ""
        elif k == "approval_required":
            validated[k] = bool(v)
        elif v is None or isinstance(v, (str, bool, int, float, dict, list)):
            validated[k] = v
        else:
            raise ValidationError(f"State update.{k} has invalid type {type(v).__name__}")
    return validated
