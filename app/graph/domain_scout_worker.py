"""
Domain Scout Worker Node
Discovers new domains not yet in the knowledge graph.
"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from app.kg.domain_scout import (
    scout_domains_from_free_sources,
    scout_social_media,
    full_domain_scout,
    get_existing_domains
)
from app.llm.client import get_llm

logger = logging.getLogger(__name__)

SCOUT_PROMPT = """You are helping to scout for new educational domains.

User request: {user_input}

Determine:
1. Should we scout free educational sources? (default: yes)
2. Should we scout social media? (default: yes, after free sources)
3. Maximum domains per source (default: 50)

Respond in JSON:
{{
    "scout_free": true,
    "scout_social": true,
    "max_domains": 50
}}
"""


async def domain_scout_node(state: AgentState) -> Dict[str, Any]:
    """
    Scout for new domains not yet in the knowledge graph.
    
    Workflow:
    1. Scout free educational sources (OpenStax, Khan Academy, MIT OCW, etc.)
    2. Scout social media (Reddit, X/Twitter)
    3. Compare against existing domains
    4. Return new domains with confidence scores
    
    Input: user_input (e.g., "scout domains" or "find new domains")
    Output: discovered_domains with recommendations
    """
    user_input = state.get("user_input", "")
    logger.info(f"Domain scouting request: {user_input[:100]}...")
    
    # Parse user intent
    llm = get_llm()
    prompt = SCOUT_PROMPT.format(user_input=user_input)
    
    try:
        response = await llm.ainvoke(prompt)
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        import json
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            scout_free = parsed.get("scout_free", True)
            scout_social = parsed.get("scout_social", True)
            max_domains = parsed.get("max_domains", 50)
        else:
            # Defaults
            scout_free = True
            scout_social = True
            max_domains = 50
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}, using defaults")
        scout_free = True
        scout_social = True
        max_domains = 50
    
    # Get existing domain count
    existing_domains = get_existing_domains()
    existing_count = len(existing_domains)
    
    # Run full scout
    results = await full_domain_scout(
        start_with_free=scout_free,
        then_social=scout_social,
        max_domains_per_source=max_domains
    )
    
    # Format response
    response_parts = []
    response_parts.append(f"🔍 Domain Scouting Results\n")
    response_parts.append(f"{'='*60}\n")
    response_parts.append(f"Existing domains in KG: {existing_count}\n")
    
    # Free educational sources results
    if results.get("free_educational"):
        free_results = results["free_educational"]
        free_stats = free_results.get("statistics", {})
        free_domains = free_results.get("discovered_domains", [])
        
        response_parts.append(f"\n📚 Free Educational Sources:")
        response_parts.append(f"   Sources Scouted: {free_stats.get('sources_scouted', 0)}")
        response_parts.append(f"   Total Discovered: {free_stats.get('total_discovered', 0)}")
        response_parts.append(f"   Unique New Domains: {free_stats.get('unique_domains', 0)}")
        response_parts.append(f"   High Confidence: {free_stats.get('high_confidence', 0)}")
        
        if free_domains:
            response_parts.append(f"\n   Top New Domains (high confidence):")
            for i, domain in enumerate(free_domains[:10], 1):
                name = domain.get("domain_name", "Unknown")
                confidence = domain.get("confidence", 0)
                source = domain.get("source", "unknown")
                response_parts.append(f"   {i}. {name} (confidence: {confidence:.2f}, from: {source})")
        
        # By source breakdown
        by_source = free_stats.get("by_source", {})
        if by_source:
            response_parts.append(f"\n   Discovered by Source:")
            for source, count in by_source.items():
                response_parts.append(f"      {source}: {count} domains")
    
    # Social media results
    if results.get("social_media"):
        social_results = results["social_media"]
        social_stats = social_results.get("statistics", {})
        social_domains = social_results.get("discovered_domains", [])
        
        response_parts.append(f"\n📱 Social Media:")
        response_parts.append(f"   Sources Scouted: {social_stats.get('sources_scouted', 0)}")
        response_parts.append(f"   Total Discovered: {social_stats.get('total_discovered', 0)}")
        response_parts.append(f"   Unique New Domains: {social_stats.get('unique_domains', 0)}")
        response_parts.append(f"   High Confidence: {social_stats.get('high_confidence', 0)}")
        
        if social_domains:
            response_parts.append(f"\n   Top Trending Domains:")
            for i, domain in enumerate(social_domains[:10], 1):
                name = domain.get("domain_name", "Unknown")
                confidence = domain.get("confidence", 0)
                source = domain.get("source", "unknown")
                response_parts.append(f"   {i}. {name} (confidence: {confidence:.2f}, from: {source})")
    
    # Combined results
    combined = results.get("combined", {})
    combined_domains = combined.get("discovered_domains", [])
    combined_stats = combined.get("statistics", {})
    
    response_parts.append(f"\n{'='*60}")
    response_parts.append(f"\n📊 Combined Results:")
    response_parts.append(f"   Total Unique New Domains: {combined_stats.get('total_unique', 0)}")
    response_parts.append(f"   From Free Sources: {combined_stats.get('from_free_sources', 0)}")
    response_parts.append(f"   From Social Media: {combined_stats.get('from_social_media', 0)}")
    
    if combined_domains:
        response_parts.append(f"\n   Top {min(15, len(combined_domains))} Recommended New Domains:")
        for i, domain in enumerate(combined_domains[:15], 1):
            name = domain.get("domain_name", "Unknown")
            confidence = domain.get("confidence", 0)
            source = domain.get("source", "unknown")
            context = domain.get("context", "")
            response_parts.append(f"   {i}. {name}")
            response_parts.append(f"      Confidence: {confidence:.2f} | Source: {source}")
            if context:
                response_parts.append(f"      Context: {context[:100]}")
    
    # Recommendations
    response_parts.append(f"\n💡 Recommendations:")
    if combined_stats.get("total_unique", 0) > 0:
        response_parts.append(f"   • {combined_stats['total_unique']} new domains discovered")
        response_parts.append(f"   • Review high-confidence domains (≥0.7) for integration")
        response_parts.append(f"   • Use '/ingest domain <name>' to add domains to taxonomy")
    else:
        response_parts.append(f"   • No new domains found - existing taxonomy is comprehensive")
        response_parts.append(f"   • Try scouting different sources or social media platforms")
    
    # Store results in state
    scouting_results = {
        "free_educational": results.get("free_educational"),
        "social_media": results.get("social_media"),
        "combined": combined,
        "existing_domains_count": existing_count
    }
    
    return {
        "scouting_results": scouting_results,
        "final_response": "\n".join(response_parts)
    }
