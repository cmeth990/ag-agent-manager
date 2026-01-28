"""
Source Discovery Module
Discovers sources from multiple providers for a given domain.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.kg.domains import get_domain_by_name
from app.kg.scoring import calculate_source_quality, get_domain_quality_threshold
from app.circuit_breaker import check_source_allowed, record_source_success, record_source_failure

logger = logging.getLogger(__name__)

# Source discovery providers
SOURCE_PROVIDERS = {
    "academic": {
        "semantic_scholar": {"enabled": True, "priority": 1},
        "arxiv": {"enabled": True, "priority": 2},
        "openalex": {"enabled": True, "priority": 3},
        "crossref": {"enabled": False, "priority": 4},  # Requires API key
    },
    "educational": {
        "openstax": {"enabled": True, "priority": 1},
        "khan_academy": {"enabled": True, "priority": 2},
        "mit_ocw": {"enabled": True, "priority": 3},
        "libretexts": {"enabled": True, "priority": 4},
    },
    "general": {
        "web_search": {"enabled": True, "priority": 1},
        "wikipedia": {"enabled": True, "priority": 2},
    }
}


async def discover_sources_for_domain(
    domain_name: str,
    max_sources: int = 20,
    min_quality: Optional[float] = None,
    source_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Discover sources for a specific domain.
    
    Args:
        domain_name: Name of the domain
        max_sources: Maximum number of sources to return
        min_quality: Minimum quality score (uses domain threshold if None)
        source_types: List of source types to search (None = all)
    
    Returns:
        Dict with:
        - sources: List of discovered sources with quality scores
        - domain_info: Domain metadata
        - statistics: Discovery statistics
        - recommendations: Recommendations for improvement
    """
    logger.info(f"Discovering sources for domain: {domain_name}")
    
    # Get domain metadata
    domain_info = get_domain_by_name(domain_name)
    if not domain_info:
        logger.warning(f"Domain {domain_name} not found in taxonomy")
        domain_info = {"domain_name": domain_name, "category_key": None}
    
    # Get quality threshold for domain (always get thresholds for recommendations)
    thresholds = get_domain_quality_threshold(domain_name)
    if min_quality is None:
        min_quality = thresholds.get("min_source_quality", 0.55)
    
    # Generate search queries for domain (now async with LLM enhancement)
    search_queries = await generate_search_queries(domain_name, domain_info)
    
    # Discover sources from all providers in parallel for better performance
    all_sources = []
    
    # Run discovery tasks in parallel
    discovery_tasks = []
    
    if not source_types or "academic" in source_types:
        discovery_tasks.append(discover_academic_sources(search_queries, domain_name))
    
    if not source_types or "educational" in source_types:
        discovery_tasks.append(discover_educational_sources(search_queries, domain_name))
    
    if not source_types or "general" in source_types:
        discovery_tasks.append(discover_general_sources(search_queries, domain_name))
    
    # Execute all discovery tasks in parallel
    if discovery_tasks:
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Source discovery task failed: {result}")
            else:
                all_sources.extend(result)
    
    # Evaluate and rank sources
    evaluated_sources = []
    for source in all_sources:
        quality_result = calculate_source_quality(source, domain_name, domain_info)
        # Ensure quality_score is always a float
        quality_score = quality_result.get("quality_score", 0.5)
        if isinstance(quality_score, (int, float)):
            quality_score = float(quality_score)
        else:
            # Try to convert string to float, default to 0.5
            try:
                quality_score = float(quality_score) if quality_score else 0.5
            except (ValueError, TypeError):
                quality_score = 0.5
        
        source["quality_score"] = quality_score
        source["quality_components"] = quality_result.get("components", {})
        source["domain_relevance"] = quality_result.get("domain_relevance", 0.5)
        source["recommendations"] = quality_result.get("recommendations", [])
        
        # Only include if meets quality threshold
        if quality_score >= min_quality:
            evaluated_sources.append(source)
    
    # Rank by priority (quality and cost)
    from app.kg.source_fetcher import rank_sources_by_priority
    ranked_sources = rank_sources_by_priority(evaluated_sources, domain_name)
    
    # Enforce source diversity - ensure we have variety across source types
    top_sources = []
    source_type_counts = {}
    max_per_type = max(1, max_sources // 3)  # Distribute across types
    
    for source in ranked_sources:
        source_type = source.get("properties", {}).get("type", "unknown")
        current_count = source_type_counts.get(source_type, 0)
        
        # Add source if we haven't exceeded max per type or haven't reached total limit
        if current_count < max_per_type or len(top_sources) < max_sources:
            top_sources.append(source)
            source_type_counts[source_type] = current_count + 1
            
            if len(top_sources) >= max_sources:
                break
    
    # If we haven't filled the quota, add remaining high-priority sources regardless of type
    if len(top_sources) < max_sources:
        for source in ranked_sources:
            if source not in top_sources:
                top_sources.append(source)
                if len(top_sources) >= max_sources:
                    break
    
    # Calculate statistics
    free_sources = [s for s in top_sources if s.get("cost_score", 1.0) == 0.0]
    paid_sources = [s for s in top_sources if s.get("cost_score", 0.0) > 0.0]
    
    stats = {
        "total_discovered": len(all_sources),
        "meets_quality_threshold": len(evaluated_sources),
        "returned": len(top_sources),
        "average_quality": sum(s["quality_score"] for s in top_sources) / len(top_sources) if top_sources else 0,
        "average_priority": sum(s.get("priority_score", 0) for s in top_sources) / len(top_sources) if top_sources else 0,
        "free_sources": len(free_sources),
        "paid_sources": len(paid_sources),
        "source_types": {}
    }
    
    # Count by type
    for source in top_sources:
        source_type = source.get("properties", {}).get("type", "unknown")
        stats["source_types"][source_type] = stats["source_types"].get(source_type, 0) + 1
    
    # Generate recommendations
    recommendations = []
    if len(top_sources) < thresholds.get("min_sources", 2):
        recommendations.append(f"Only {len(top_sources)} sources found. Need at least {thresholds.get('min_sources', 2)} for {domain_info.get('difficulty', 'intermediate')} level.")
    
    if stats["average_quality"] < min_quality:
        recommendations.append(f"Average source quality ({stats['average_quality']:.2f}) below threshold ({min_quality:.2f}). Consider expanding search.")
    
    # Check diversity
    unique_types = len(stats["source_types"])
    if unique_types < 2:
        recommendations.append("Low source diversity. Seek different source types.")
    
    return {
        "sources": top_sources,
        "domain_info": domain_info,
        "statistics": stats,
        "recommendations": recommendations,
        "quality_threshold": min_quality
    }


async def generate_search_queries(domain_name: str, domain_info: Dict[str, Any]) -> List[str]:
    """
    Generate intelligent search queries for a domain using LLM when available.
    
    Returns:
        List of search query strings optimized for source discovery
    """
    queries = [domain_name]
    
    # Basic variations (always include)
    if " " in domain_name:
        words = domain_name.split()
        queries.append(" ".join(words[:2]))  # First two words
        if len(words) > 1:
            queries.append(words[0])  # First word only
    
    # Add category-based queries
    category = domain_info.get("category_key")
    if category:
        queries.append(f"{domain_name} {category}")
    
    # Add difficulty/gradeband context
    difficulty = domain_info.get("difficulty")
    gradebands = domain_info.get("gradebands", [])
    if gradebands:
        queries.append(f"{domain_name} {gradebands[0]}")
    
    # Use LLM to generate additional optimized queries for better results
    try:
        from app.llm.client import get_llm
        llm = get_llm()
        
        prompt = f"""Generate 3-5 optimized search queries for finding educational sources about "{domain_name}".

Context:
- Domain: {domain_name}
- Category: {category or 'unknown'}
- Difficulty: {difficulty or 'intermediate'}
- Grade Level: {', '.join(gradebands) if gradebands else 'general'}

Generate search queries that would find:
1. Academic papers and research
2. Educational textbooks and courses
3. Online learning resources

Make queries:
- Specific enough to find relevant sources
- Varied to cover different aspects of the domain
- Include synonyms and related terms when helpful

Respond with a JSON array of query strings:
["query1", "query2", "query3"]
"""
        
        # Add timeout to prevent hanging
        response = await asyncio.wait_for(
            llm.ainvoke(prompt),
            timeout=10.0  # 10 second timeout for query generation
        )
        
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        # Parse JSON response
        import re
        import json
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            llm_queries = json.loads(json_match.group())
            # Add LLM queries that aren't duplicates
            for q in llm_queries:
                q_clean = q.strip()
                if q_clean and q_clean.lower() not in [q.lower() for q in queries]:
                    queries.append(q_clean)
        
        logger.info(f"Generated {len(queries)} search queries for {domain_name} (including LLM-enhanced)")
    except asyncio.TimeoutError:
        logger.warning(f"LLM query generation timed out for {domain_name}, using basic queries only")
    except Exception as e:
        logger.warning(f"LLM query generation failed for {domain_name}: {e}, using basic queries only")
    
    return list(set(queries))  # Remove duplicates


async def discover_academic_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover academic sources (papers, books, journals).
    
    Uses real APIs:
    - Semantic Scholar API
    - arXiv API
    - OpenAlex API
    
    Now runs API calls in parallel for better performance.
    """
    sources = []
    
    from app.kg.api_clients import search_semantic_scholar, search_arxiv, search_openalex
    
    # Use best query (first one, usually the domain name)
    query = queries[0] if queries else domain_name
    
    # Run all academic API searches in parallel (skip providers blocked by circuit breaker)
    search_tasks = []
    provider_keys = []
    if SOURCE_PROVIDERS["academic"]["semantic_scholar"]["enabled"] and check_source_allowed("semantic_scholar"):
        search_tasks.append(search_semantic_scholar(query, limit=5, domain=domain_name))
        provider_keys.append("semantic_scholar")
    if SOURCE_PROVIDERS["academic"]["arxiv"]["enabled"] and check_source_allowed("arxiv"):
        search_tasks.append(search_arxiv(query, limit=5, domain=domain_name))
        provider_keys.append("arxiv")
    if SOURCE_PROVIDERS["academic"]["openalex"]["enabled"] and check_source_allowed("openalex"):
        search_tasks.append(search_openalex(query, limit=5, domain=domain_name))
        provider_keys.append("openalex")
    
    if search_tasks:
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            key = provider_keys[i] if i < len(provider_keys) else "unknown"
            if isinstance(result, Exception):
                record_source_failure(key)
                logger.warning(f"Academic source {key} search failed: {result}")
            else:
                record_source_success(key)
                for source in result:
                    source["properties"]["domain"] = domain_name
                sources.extend(result)
    
    logger.info(f"Discovered {len(sources)} academic sources for {domain_name}")
    return sources


async def discover_educational_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover educational sources (OER, courses, textbooks).
    
    Uses real APIs where available:
    - OpenStax (web search)
    - Khan Academy (URL construction)
    - MIT OCW (URL construction)
    
    Now runs API calls in parallel for better performance.
    """
    sources = []
    
    from app.kg.api_clients import search_openstax, search_khan_academy, search_mit_ocw
    
    # Use best query (first one, usually the domain name)
    query = queries[0] if queries else domain_name
    
    # Run all educational API searches in parallel (skip providers blocked by circuit breaker)
    search_tasks = []
    provider_keys = []
    if SOURCE_PROVIDERS["educational"]["openstax"]["enabled"] and check_source_allowed("openstax"):
        search_tasks.append(search_openstax(query, limit=3))
        provider_keys.append("openstax")
    if SOURCE_PROVIDERS["educational"]["khan_academy"]["enabled"] and check_source_allowed("khan_academy"):
        search_tasks.append(search_khan_academy(query, limit=3))
        provider_keys.append("khan_academy")
    if SOURCE_PROVIDERS["educational"]["mit_ocw"]["enabled"] and check_source_allowed("mit_ocw"):
        search_tasks.append(search_mit_ocw(query, limit=3))
        provider_keys.append("mit_ocw")
    
    if search_tasks:
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            key = provider_keys[i] if i < len(provider_keys) else "unknown"
            if isinstance(result, Exception):
                record_source_failure(key)
                logger.warning(f"Educational source {key} search failed: {result}")
            else:
                record_source_success(key)
                for source in result:
                    source["properties"]["domain"] = domain_name
                sources.extend(result)
    
    logger.info(f"Discovered {len(sources)} educational sources for {domain_name}")
    return sources


async def discover_general_sources(queries: List[str], domain_name: str) -> List[Dict[str, Any]]:
    """
    Discover general sources (web, Wikipedia, etc.).
    
    Uses real APIs:
    - Wikipedia REST API
    """
    sources = []
    
    from app.kg.api_clients import search_wikipedia
    
    for query in queries[:1]:  # Limit queries
        if SOURCE_PROVIDERS["general"]["wikipedia"]["enabled"] and check_source_allowed("wikipedia"):
            try:
                wiki_sources = await search_wikipedia(query, limit=3, domain=domain_name)
                record_source_success("wikipedia")
                for source in wiki_sources:
                    source["properties"]["domain"] = domain_name
                sources.extend(wiki_sources)
            except Exception as e:
                record_source_failure("wikipedia")
                logger.warning(f"Wikipedia search failed: {e}")
    
    logger.info(f"Discovered {len(sources)} general sources for {domain_name}")
    return sources


# API client functions moved to app.kg.api_clients module
# Import them when needed:
# from app.kg.api_clients import (
#     search_semantic_scholar,
#     search_arxiv,
#     search_openalex,
#     search_wikipedia,
#     search_openstax,
#     search_khan_academy,
#     search_mit_ocw
# )
