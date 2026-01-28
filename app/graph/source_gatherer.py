"""
Source Gatherer Worker Node
Discovers and evaluates sources for domains.
"""
import logging
from typing import Dict, Any, List
from app.graph.state import AgentState
from app.validation.agent_outputs import validate_source_gatherer_output, ValidationError
from app.kg.source_discovery import discover_sources_for_domain
from app.kg.source_fetcher import (
    gather_domain_content_prioritized,
    rank_sources_by_priority,
    calculate_source_cost
)
from app.kg.domains import get_domain_by_name, get_domains_by_category
from app.kg.scoring import calculate_source_quality, get_domain_quality_threshold
from app.kg.knowledge_base import generate_id, NODE_TYPES
from app.llm.tiering import get_llm_for_task
from app.security.prompt_injection import wrap_untrusted_content

logger = logging.getLogger(__name__)

SOURCE_GATHERING_PROMPT = """You are a source discovery expert helping to find high-quality sources for educational domains.

Your task is to:
1. Identify the domain(s) the user wants sources for (even if not in the available list - extract the domain name from the request)
2. Generate effective search queries for that domain
3. Suggest source types that would be most valuable (academic papers, textbooks, courses, etc.)

User request: {user_input}

Available domains (for reference): {available_domains}

IMPORTANT: Extract the domain name from the user request even if it's not in the available domains list.
For example, if the user says "gather sources for American Revolution", extract "American Revolution" as the domain.

For the identified domain(s), provide:
1. Domain name(s) - extract from the request, use exact name mentioned
2. Search queries (3-5 queries that would find good sources)
3. Recommended source types (academic, educational, general)
4. Any specific requirements (grade level, difficulty, recency)

Respond in JSON format:
{{
    "domains": ["domain1", "domain2"],
    "search_queries": ["query1", "query2", "query3"],
    "source_types": ["academic", "educational"],
    "requirements": {{
        "grade_level": "9-12",
        "difficulty": "intermediate",
        "min_quality": 0.65
    }}
}}
"""


async def source_gatherer_node(state: AgentState) -> Dict[str, Any]:
    """
    Discover and evaluate sources for one or more domains.
    
    Input: user_input (domain name or request)
    Output: discovered_sources with quality scores
    
    Supports:
    - Single domain: "gather sources for Algebra"
    - Multiple domains: "gather sources for Algebra and Geometry"
    - Category: "gather sources for all mathematics domains"
    """
    user_input = state.get("user_input", "")
    logger.info(f"Source gathering request: {user_input[:100]}...")
    
    # Cheap tier: source_filtering uses smaller model
    domain = (state.get("discovered_sources") or {}).get("domains", [None])[0] if isinstance(state.get("discovered_sources"), dict) else None
    queue = state.get("queue", "source_gathering")
    llm = get_llm_for_task("source_filtering", domain=domain, queue=queue, agent="source_gatherer")
    
    # Get available domains for context
    available_domains = []
    try:
        from app.kg.domains import DOMAIN_TAXONOMY
        for category, domains in DOMAIN_TAXONOMY.items():
            available_domains.extend(list(domains.keys())[:10])  # Sample
    except:
        pass
    
    if not llm:
        domains = extract_domains_from_text(user_input, available_domains)
        search_queries = [d for d in domains]
        source_types = ["academic", "educational", "general"]
        requirements = {}
    else:
        # Prompt injection defense: treat user input as untrusted
        safe_input = wrap_untrusted_content(user_input, max_length=10_000)
        prompt = SOURCE_GATHERING_PROMPT.format(
            user_input=safe_input,
            available_domains=", ".join(available_domains[:20])
        )
    
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
                domains = parsed.get("domains", [])
                search_queries = parsed.get("search_queries", [])
                source_types = parsed.get("source_types", ["academic", "educational", "general"])
                requirements = parsed.get("requirements", {})
            else:
                domains = extract_domains_from_text(user_input, available_domains)
                search_queries = [d for d in domains]
                source_types = ["academic", "educational", "general"]
                requirements = {}
        else:
            domains = extract_domains_from_text(user_input, available_domains)
            search_queries = [d for d in domains]
            source_types = ["academic", "educational", "general"]
            requirements = {}
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}, using fallback")
        domains = extract_domains_from_text(user_input, available_domains)
        search_queries = domains
        source_types = ["academic", "educational", "general"]
        requirements = {}
    
    if not domains:
        out = {
            "final_response": f"❌ Could not identify domain(s) from: {user_input}\n\nPlease specify a domain name, e.g., 'gather sources for Algebra' or 'find sources for Machine Learning'."
        }
        try:
            return validate_source_gatherer_output(out)
        except ValidationError:
            return out
    
    # Discover sources for each domain
    all_discovered = {}
    all_sources = []
    
    for domain in domains:
        logger.info(f"Discovering sources for domain: {domain}")
        
        # Get requirements
        min_quality = requirements.get("min_quality")
        max_sources = requirements.get("max_sources", 20)
        
        # Discover sources
        result = await discover_sources_for_domain(
            domain_name=domain,
            max_sources=max_sources,
            min_quality=min_quality,
            source_types=source_types if source_types else None
        )
        
        all_discovered[domain] = result
        all_sources.extend(result["sources"])
    
    # Format response
    response_parts = []
    response_parts.append(f"📚 Source Discovery Results\n")
    response_parts.append(f"{'='*60}\n")
    
    for domain, result in all_discovered.items():
        sources = result["sources"]
        stats = result["statistics"]
        domain_info = result["domain_info"]
        
        response_parts.append(f"\n🔍 Domain: {domain}")
        if domain_info.get("category_key"):
            response_parts.append(f"   Category: {domain_info.get('category_key')}")
        if domain_info.get("difficulty"):
            response_parts.append(f"   Difficulty: {domain_info.get('difficulty')}")
        
        total_d = stats.get("total_discovered", 0)
        meets = stats.get("meets_quality_threshold", len(sources))
        response_parts.append(f"\n   Found {len(sources)} high-quality sources (quality ≥ {result['quality_threshold']:.2f})")
        if total_d > 0 and (total_d != meets or (total_d > 0 and len(sources) == 0)):
            response_parts.append(f"   (Discovered: {total_d} | Met threshold: {meets})")
        response_parts.append(f"   Average Quality: {stats['average_quality']:.3f}")
        response_parts.append(f"   Average Priority: {stats.get('average_priority', 0):.3f}")
        response_parts.append(f"   Free Sources: {stats.get('free_sources', 0)} | Paid: {stats.get('paid_sources', 0)}")
        response_parts.append(f"   Source Types: {', '.join(stats['source_types'].keys())}")
        
        # Top 5 sources (ranked by priority)
        response_parts.append(f"\n   Top Sources (ranked by priority - high quality & free first):")
        for i, source in enumerate(sources[:5], 1):
            props = source.get("properties", {})
            title = props.get("title", "Unknown")
            quality = source.get("quality_score", 0)
            cost = source.get("cost_score", 0)
            priority = source.get("priority_score", 0)
            cost_tier = source.get("cost_tier", "unknown")
            source_type = props.get("type", "unknown")
            year = props.get("year", "?")
            cost_label = "FREE" if cost == 0.0 else f"${cost_tier.upper()}"
            response_parts.append(f"   {i}. {title} ({source_type}, {year})")
            response_parts.append(f"      Quality: {quality:.3f} | Cost: {cost_label} | Priority: {priority:.3f}")
        
        # Recommendations
        if result.get("recommendations"):
            response_parts.append(f"\n   ⚠️  Recommendations:")
            for rec in result["recommendations"]:
                response_parts.append(f"      • {rec}")
    
    # Summary
    total_free = sum(len([s for s in r["sources"] if s.get("cost_score", 1.0) == 0.0]) for r in all_discovered.values())
    total_paid = sum(len([s for s in r["sources"] if s.get("cost_score", 0.0) > 0.0]) for r in all_discovered.values())
    
    response_parts.append(f"\n{'='*60}")
    response_parts.append(f"\n📊 Summary:")
    response_parts.append(f"   Total Domains: {len(domains)}")
    response_parts.append(f"   Total Sources: {len(all_sources)}")
    response_parts.append(f"   Free Sources: {total_free} | Paid: {total_paid}")
    response_parts.append(f"   Average Quality: {sum(s.get('quality_score', 0) for s in all_sources) / len(all_sources) if all_sources else 0:.3f}")
    response_parts.append(f"   Average Priority: {sum(s.get('priority_score', 0) for s in all_sources) / len(all_sources) if all_sources else 0:.3f}")
    
    # Option to fetch content
    response_parts.append(f"\n💡 Next Step: Use '/fetch content for {domains[0]}' to gather actual content from top sources")
    
    # Store discovered sources in state for potential KG insertion
    discovered_sources = {
        "domains": domains,
        "sources_by_domain": all_discovered,
        "all_sources": all_sources,
        "statistics": {
            "total_sources": len(all_sources),
            "domains_covered": len(domains),
            "average_quality": sum(s.get("quality_score", 0) for s in all_sources) / len(all_sources) if all_sources else 0,
            "average_priority": sum(s.get("priority_score", 0) for s in all_sources) / len(all_sources) if all_sources else 0,
            "free_sources": total_free,
            "paid_sources": total_paid
        }
    }
    
    out = {
        "discovered_sources": discovered_sources,
        "final_response": "\n".join(response_parts)
    }
    try:
        return validate_source_gatherer_output(out)
    except ValidationError as e:
        logger.warning(f"Source gatherer output validation failed: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ Validation error: {e}. Please try again or use a different domain."
        }


def extract_domains_from_text(text: str, available_domains: List[str]) -> List[str]:
    """
    Extract domain names from text using pattern extraction or matching.
    """
    import re
    
    # First, try to extract domain from common patterns like "for X" or "gather sources for X"
    # Improved patterns to capture multi-word domains like "American Revolution"
    patterns = [
        r'(?:gather|find|get|search for|discover|fetch).*?for\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|\.|and)',
        r'for\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|\.|and)',
        r'domain[s]?[:\s]+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|\.)',
    ]
    
    extracted = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            domain = match.strip()
            # Clean up common trailing words
            domain = re.sub(r'\s+(sources?|content|materials?)$', '', domain, flags=re.IGNORECASE)
            if domain and len(domain) > 2 and len(domain) < 100:
                extracted.append(domain)
    
    if extracted:
        return extracted[:1]  # Return first extracted domain
    
    # Fallback: try matching against available domains
    text_lower = text.lower()
    found_domains = []
    
    for domain in available_domains:
        domain_lower = domain.lower()
        # Check for exact match or word match
        if domain_lower in text_lower or any(word in text_lower for word in domain_lower.split() if len(word) > 3):
            found_domains.append(domain)
    
    # Also check for common patterns with title case
    pattern = r'(?:for|about|on)\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|,|and)'
    matches = re.findall(pattern, text)
    for match in matches:
        match = match.strip()
        if match and len(match) > 2:
            # Check if it matches any available domain
            for domain in available_domains:
                if match.lower() in domain.lower() or domain.lower() in match.lower():
                    if domain not in found_domains:
                        found_domains.append(domain)
    
    return found_domains[:5] if found_domains else extracted[:1]  # Return extracted if no matches found


async def gather_sources_for_all_domains_in_category(
    category_key: str,
    max_sources_per_domain: int = 10
) -> Dict[str, Any]:
    """
    Gather sources for all domains in a category.
    
    Useful for bulk source discovery.
    """
    domains = get_domains_by_category(category_key)
    
    all_results = {}
    for domain in domains:
        result = await discover_sources_for_domain(
            domain_name=domain,
            max_sources=max_sources_per_domain
        )
        all_results[domain] = result
    
    return {
        "category": category_key,
        "domains": domains,
        "results": all_results,
        "total_sources": sum(len(r["sources"]) for r in all_results.values())
    }
