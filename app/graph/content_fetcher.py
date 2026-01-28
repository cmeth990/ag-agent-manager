"""
Content Fetcher Worker Node
Fetches actual content from discovered sources in priority order.
"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from app.kg.source_fetcher import gather_domain_content_prioritized
from app.kg.source_discovery import discover_sources_for_domain
from app.llm.tiering import get_llm_for_task
from app.security.prompt_injection import wrap_untrusted_content
from app.validation.agent_outputs import validate_content_fetcher_parsed, ValidationError

logger = logging.getLogger(__name__)

CONTENT_FETCHING_PROMPT = """You are helping to fetch content from sources for a domain.

User request: {user_input}

Extract:
1. Domain name(s)
2. Maximum number of sources to fetch (default: 10)
3. Minimum priority threshold (default: 0.0)

Respond in JSON:
{{
    "domains": ["domain1"],
    "max_sources": 10,
    "min_priority": 0.0
}}
"""


async def content_fetcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Fetch actual content from discovered sources in priority order.
    
    Priority: High confidence & free first, low confidence & costly last.
    
    Input: user_input (e.g., "fetch content for Algebra")
    Output: fetched_content with source content
    """
    user_input = state.get("user_input", "")
    logger.info(f"Content fetching request: {user_input[:100]}...")
    
    # Check if we have discovered sources in state
    discovered_sources = state.get("discovered_sources", {})
    
    # Cheap tier: classification for domain/params extraction
    domain = (state.get("discovered_sources") or {}).get("domains", [None])[0] if isinstance(state.get("discovered_sources"), dict) else None
    llm = get_llm_for_task("classification", domain=domain, queue="content_fetch", agent="content_fetcher")
    
    if not llm:
        domains = extract_domains_from_text(user_input)
        max_sources = 10
        min_priority = 0.0
    else:
        safe_input = wrap_untrusted_content(user_input, max_length=10_000)
        prompt = CONTENT_FETCHING_PROMPT.format(user_input=safe_input)
    try:
        if llm:
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
                try:
                    parsed = validate_content_fetcher_parsed(parsed)
                except ValidationError as ve:
                    logger.warning(f"Content fetcher parsed output validation: {ve}; using defaults")
                    parsed = {"domains": [], "max_sources": 10, "min_priority": 0.0}
                domains = parsed.get("domains", [])
                max_sources = parsed.get("max_sources", 10)
                min_priority = parsed.get("min_priority", 0.0)
            else:
                domains = extract_domains_from_text(user_input)
                max_sources = 10
                min_priority = 0.0
        else:
            pass  # domains, max_sources, min_priority set above
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}, using fallback")
        domains = extract_domains_from_text(user_input)
        max_sources = 10
        min_priority = 0.0
    
    if not domains:
        return {
            "final_response": f"❌ Could not identify domain(s) from: {user_input}\n\nPlease specify a domain, e.g., 'fetch content for Algebra'"
        }
    
    # Use discovered sources if available, otherwise discover new ones
    all_fetched = {}
    
    for domain in domains:
        logger.info(f"Fetching content for domain: {domain}")
        
        # Get sources for this domain
        if discovered_sources and domain in discovered_sources.get("sources_by_domain", {}):
            sources = discovered_sources["sources_by_domain"][domain]["sources"]
        else:
            # Discover sources first
            discovery_result = await discover_sources_for_domain(domain_name=domain, max_sources=max_sources * 2)
            sources = discovery_result["sources"]
        
        # Fetch content in priority order
        fetch_result = await gather_domain_content_prioritized(
            sources=sources,
            domain_name=domain,
            max_sources=max_sources,
            min_priority=min_priority
        )
        
        all_fetched[domain] = fetch_result
    
    # Format response
    response_parts = []
    response_parts.append(f"📥 Content Fetching Results\n")
    response_parts.append(f"{'='*60}\n")
    
    for domain, result in all_fetched.items():
        fetched_sources = result["fetched_sources"]
        stats = result["statistics"]
        
        response_parts.append(f"\n🔍 Domain: {domain}")
        response_parts.append(f"   Sources Fetched: {stats['successful_fetches']}/{stats['total_sources']}")
        response_parts.append(f"   Free Sources: {stats['free_sources']} | Paid: {stats['paid_sources']}")
        response_parts.append(f"   Total Content: {stats['total_content_length']:,} characters")
        response_parts.append(f"   Average Quality: {stats['average_quality']:.3f}")
        response_parts.append(f"   Average Priority: {stats['average_priority']:.3f}")
        
        # Show fetched sources
        response_parts.append(f"\n   Fetched Sources (priority order):")
        for i, source in enumerate(fetched_sources[:5], 1):
            props = source.get("properties", {})
            title = props.get("title", "Unknown")
            quality = source.get("quality_score", 0)
            cost_tier = source.get("cost_tier", "unknown")
            priority = source.get("priority_score", 0)
            fetched = source.get("fetched_content", {})
            accessible = fetched.get("accessible", False)
            
            status = "✅" if accessible else "❌"
            cost_label = "FREE" if source.get("cost_score", 1.0) == 0.0 else f"${cost_tier.upper()}"
            
            response_parts.append(f"   {i}. {status} {title}")
            response_parts.append(f"      Quality: {quality:.3f} | Cost: {cost_label} | Priority: {priority:.3f}")
            
            if accessible:
                content = fetched.get("content", "")
                content_preview = content[:200] + "..." if len(content) > 200 else content
                response_parts.append(f"      Content preview: {content_preview}")
            else:
                error = fetched.get("metadata", {}).get("error", "Unknown error")
                response_parts.append(f"      Error: {error}")
        
        # Recommendations
        if result.get("recommendations"):
            response_parts.append(f"\n   ⚠️  Recommendations:")
            for rec in result["recommendations"]:
                response_parts.append(f"      • {rec}")
    
    # Summary
    total_fetched = sum(r["statistics"]["successful_fetches"] for r in all_fetched.values())
    total_failed = sum(r["statistics"]["failed_fetches"] for r in all_fetched.values())
    total_free = sum(r["statistics"]["free_sources"] for r in all_fetched.values())
    
    response_parts.append(f"\n{'='*60}")
    response_parts.append(f"\n📊 Summary:")
    response_parts.append(f"   Domains: {len(domains)}")
    response_parts.append(f"   Successfully Fetched: {total_fetched}")
    response_parts.append(f"   Failed: {total_failed}")
    response_parts.append(f"   Free Sources: {total_free}")
    response_parts.append(f"\n💡 Content is ready for extraction and ingestion into the knowledge graph")
    
    # Store fetched content in state
    fetched_content = {
        "domains": domains,
        "content_by_domain": all_fetched,
        "statistics": {
            "total_fetched": total_fetched,
            "total_failed": total_failed,
            "total_free": total_free
        }
    }
    
    return {
        "fetched_content": fetched_content,
        "final_response": "\n".join(response_parts)
    }


def extract_domains_from_text(text: str) -> list:
    """Extract domain names from text."""
    # Simple extraction - look for "for <domain>" pattern
    import re
    pattern = r'(?:for|about|on)\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|and)'
    matches = re.findall(pattern, text)
    return [m.strip() for m in matches if len(m.strip()) > 2]
