"""
Domain Scout Module
Discovers new domains not yet in the knowledge graph by scraping educational platforms
and social media to identify emerging or missing domains.
"""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse, quote
import re
import json
from app.kg.domains import DOMAIN_TAXONOMY, get_domain_by_name, get_domains_by_category
from app.llm.client import get_llm
from app.security.network import is_url_allowed
from app.security.sanitize import sanitize_content, sanitize_for_llm
from app.security.prompt_injection import wrap_untrusted_content

# Import re at module level
import re

logger = logging.getLogger(__name__)

# Free educational sources to scout first
SCOUT_SOURCES = {
    "free_educational": {
        "openstax": {
            "enabled": True,
            "priority": 1,
            "base_url": "https://openstax.org",
            "subjects_url": "https://openstax.org/subjects",
            "scraping_method": "web_scrape"
        },
        "khan_academy": {
            "enabled": True,
            "priority": 2,
            "base_url": "https://www.khanacademy.org",
            "subjects_url": "https://www.khanacademy.org/subjects",
            "scraping_method": "api_or_scrape"
        },
        "mit_ocw": {
            "enabled": True,
            "priority": 3,
            "base_url": "https://ocw.mit.edu",
            "subjects_url": "https://ocw.mit.edu/courses",
            "scraping_method": "web_scrape"
        },
        "coursera": {
            "enabled": True,
            "priority": 4,
            "base_url": "https://www.coursera.org",
            "subjects_url": "https://www.coursera.org/browse",
            "scraping_method": "web_scrape"
        },
        "edx": {
            "enabled": True,
            "priority": 5,
            "base_url": "https://www.edx.org",
            "subjects_url": "https://www.edx.org/search",
            "scraping_method": "web_scrape"
        }
    },
    "social_media": {
        "reddit": {
            "enabled": True,
            "priority": 1,
            "base_url": "https://www.reddit.com",
            "api_url": "https://www.reddit.com/r/learnmath/search.json",
            "scraping_method": "reddit_api"
        },
        "twitter": {
            "enabled": True,
            "priority": 2,
            "base_url": "https://x.com",
            "scraping_method": "web_scrape"  # Note: Twitter/X requires API key for real access
        }
    }
}

# Existing domains cache (for comparison)
_existing_domains_cache: Optional[Set[str]] = None


def get_existing_domains() -> Set[str]:
    """Get set of all existing domain names from taxonomy."""
    global _existing_domains_cache
    
    if _existing_domains_cache is None:
        _existing_domains_cache = set()
        for category, domains in DOMAIN_TAXONOMY.items():
            if isinstance(domains, dict):
                _existing_domains_cache.update(domains.keys())
    
    return _existing_domains_cache


async def scout_domains_from_free_sources(
    max_domains_per_source: int = 50,
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Scout free educational sources to discover new domains.
    
    Args:
        max_domains_per_source: Max domains to extract per source
        min_confidence: Minimum confidence for domain extraction
    
    Returns:
        Dict with discovered domains, statistics, and recommendations
    """
    logger.info("Starting domain scouting from free educational sources")
    
    existing_domains = get_existing_domains()
    all_discovered = []
    source_results = {}
    
    # Scout free educational sources (limit to first 3 to avoid timeout)
    sources_to_scout = list(SCOUT_SOURCES["free_educational"].items())[:3]
    for source_name, source_config in sources_to_scout:
        if not source_config.get("enabled", False):
            continue
        
        logger.info(f"Scouting {source_name}...")
        
        try:
            # Add timeout per source
            discovered = await asyncio.wait_for(
                scout_source(
                    source_name=source_name,
                    source_config=source_config,
                    existing_domains=existing_domains,
                    max_domains=max_domains_per_source
                ),
                timeout=30.0  # 30 second timeout per source
            )
            
            source_results[source_name] = discovered
            all_discovered.extend(discovered.get("domains", []))
            
            logger.info(f"  Found {len(discovered.get('domains', []))} potential new domains from {source_name}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Scouting {source_name} timed out after 30 seconds")
            source_results[source_name] = {
                "domains": [],
                "error": "Timeout after 30 seconds"
            }
        except Exception as e:
            logger.error(f"Error scouting {source_name}: {e}")
            source_results[source_name] = {
                "domains": [],
                "error": str(e)
            }
    
    # Deduplicate and rank discovered domains
    unique_domains = deduplicate_domains(all_discovered)
    
    # Filter by confidence
    high_confidence = [d for d in unique_domains if d.get("confidence", 0) >= min_confidence]
    
    # Sort by confidence (descending)
    high_confidence.sort(key=lambda d: d.get("confidence", 0), reverse=True)
    
    statistics = {
        "total_discovered": len(all_discovered),
        "unique_domains": len(unique_domains),
        "high_confidence": len(high_confidence),
        "sources_scouted": len([r for r in source_results.values() if r.get("domains")]),
        "by_source": {
            name: len(result.get("domains", []))
            for name, result in source_results.items()
        }
    }
    
    return {
        "discovered_domains": high_confidence,
        "all_discovered": unique_domains,
        "source_results": source_results,
        "statistics": statistics,
        "existing_domains_count": len(existing_domains)
    }


async def scout_source(
    source_name: str,
    source_config: Dict[str, Any],
    existing_domains: Set[str],
    max_domains: int = 50
) -> Dict[str, Any]:
    """
    Scout a specific source for domains.
    
    Args:
        source_name: Name of the source (e.g., "openstax")
        source_config: Source configuration
        existing_domains: Set of existing domain names
        max_domains: Maximum domains to extract
    
    Returns:
        Dict with discovered domains and metadata
    """
    method = source_config.get("scraping_method", "web_scrape")
    
    if method == "web_scrape":
        return await scout_web_source(source_name, source_config, existing_domains, max_domains)
    elif method == "reddit_api":
        return await scout_reddit(source_name, source_config, existing_domains, max_domains)
    elif method == "api_or_scrape":
        # Try API first, fallback to scraping
        try:
            return await scout_api_source(source_name, source_config, existing_domains, max_domains)
        except:
            return await scout_web_source(source_name, source_config, existing_domains, max_domains)
    else:
        return {"domains": [], "error": f"Unknown scraping method: {method}"}


async def scout_web_source(
    source_name: str,
    source_config: Dict[str, Any],
    existing_domains: Set[str],
    max_domains: int
) -> Dict[str, Any]:
    """
    Scout a web source by scraping HTML.
    """
    url = source_config.get("subjects_url") or source_config.get("base_url")
    discovered = []

    # Network egress control: only fetch from allowlisted domains
    if not url or not is_url_allowed(url):
        logger.warning(f"Domain scout: URL not in allowlist, skipping: {url}")
        return {"discovered_domains": discovered, "statistics": {"sources_scouted": 0, "total_discovered": 0, "unique_domains": 0, "high_confidence": 0, "by_source": {}}}

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; DomainScoutBot/1.0; +https://example.com/bot)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    html = await response.text()
                    # Content sanitization: strip scripts, hidden text
                    html = sanitize_content(html, content_type="html", max_length=500_000)
                    # First, try simple HTML parsing for common patterns
                    simple_domains = extract_domains_simple(html, source_name, existing_domains)
                    discovered.extend(simple_domains)
                    
                    # Only use LLM if we haven't found enough domains via simple parsing
                    # AND limit to one LLM call per source to avoid excessive API usage
                    if len(discovered) < max_domains * 0.5:  # Only if we found less than 50% of target
                        try:
                            # Add timeout to LLM call
                            llm_domains = await asyncio.wait_for(
                                extract_domains_from_html(html, source_name, existing_domains),
                                timeout=30.0  # 30 second timeout for LLM extraction
                            )
                            # Add LLM domains that aren't already found
                            existing_names = {d["domain_name"].lower() for d in discovered}
                            for domain in llm_domains:
                                if domain["domain_name"].lower() not in existing_names:
                                    discovered.append(domain)
                                    if len(discovered) >= max_domains:
                                        break
                        except asyncio.TimeoutError:
                            logger.warning(f"LLM extraction timed out for {source_name}, using simple parsing results only")
                        except Exception as e:
                            logger.warning(f"LLM extraction failed for {source_name}: {e}, using simple parsing results only")
                    
                    # Limit to max_domains
                    discovered = discovered[:max_domains]
    
    except Exception as e:
        logger.error(f"Error scouting web source {source_name}: {e}")
        return {"domains": [], "error": str(e)}
    
    return {
        "domains": discovered,
        "source": source_name,
        "url": url,
        "method": "web_scrape"
    }


def extract_domains_simple(html: str, source_name: str, existing_domains: Set[str]) -> List[Dict[str, Any]]:
    """
    Simple HTML parsing to extract domain names from common patterns.
    """
    domains = []
    
    # Patterns to look for:
    # - Links with educational keywords
    # - Headings (h1, h2, h3) that look like domain names
    # - List items in course/subject listings
    
    import re
    
    # Extract from links (common in course listings)
    link_pattern = r'<a[^>]*>(.*?)</a>'
    links = re.findall(link_pattern, html, re.IGNORECASE)
    
    for link_text in links:
        # Clean HTML tags
        text = re.sub(r'<[^>]+>', '', link_text).strip()
        
        # Check if it looks like a domain name
        if is_likely_domain_name(text, existing_domains):
            domains.append({
                "domain_name": text,
                "confidence": 0.7,  # Medium confidence for simple extraction
                "source": source_name,
                "context": "Link text",
                "method": "simple_html"
            })
    
    # Extract from headings
    heading_pattern = r'<h[1-3][^>]*>(.*?)</h[1-3]>'
    headings = re.findall(heading_pattern, html, re.IGNORECASE)
    
    for heading in headings:
        text = re.sub(r'<[^>]+>', '', heading).strip()
        if is_likely_domain_name(text, existing_domains):
            domains.append({
                "domain_name": text,
                "confidence": 0.75,
                "source": source_name,
                "context": "Heading",
                "method": "simple_html"
            })
    
    # Deduplicate
    seen = set()
    unique_domains = []
    for domain in domains:
        name_lower = domain["domain_name"].lower()
        if name_lower not in seen:
            seen.add(name_lower)
            unique_domains.append(domain)
    
    return unique_domains


def is_likely_domain_name(text: str, existing_domains: Set[str]) -> bool:
    """
    Check if text looks like an educational domain name.
    """
    if not text or len(text) < 3 or len(text) > 100:
        return False
    
    # Skip if already exists
    if text.lower() in existing_domains:
        return False
    
    # Skip generic terms (expanded list)
    generic_terms = [
        "home", "about", "contact", "login", "sign up", "search", "menu",
        "introduction", "overview", "welcome", "learn more", "read more",
        "click here", "next", "previous", "back", "skip", "give now",
        "help", "faq", "faqs", "for individuals", "for businesses", "for universities",
        "for governments", "join for free", "log in", "sign in", "register",
        "terms", "privacy", "cookie", "accessibility", "sitemap", "careers",
        "blog", "news", "events", "support", "documentation", "api",
        "about ocw", "contact us", "about us", "get started", "sign in", "log in"
    ]
    text_lower_clean = text.lower().strip()
    if text_lower_clean in generic_terms:
        return False
    
    # Skip if starts with generic navigation words
    if text_lower_clean.startswith(("about ", "contact ", "help ", "faq", "login", "sign in", "log in", "register", "get started")):
        return False
    
    # Skip navigation/UI elements
    if any(nav_term in text.lower() for nav_term in ["&amp;", "&", "amp;", "faqs", "faq"]):
        if text.lower() in ["help & faqs", "help &amp; faqs", "help and faqs"]:
            return False
    
    # Skip if too many numbers or special chars
    if len(re.findall(r'[0-9]', text)) > len(text) * 0.3:
        return False
    
    # Skip URLs
    if text.startswith("http") or "/" in text or ("." in text and len(text.split(".")) > 2):
        return False
    
    # Skip if it's clearly navigation (repeated words, all caps, etc.)
    words = text.split()
    if len(words) > 1 and words[0].lower() == words[-1].lower():
        return False  # "Arts and HumanitiesArts and Humanities"
    
    if text.isupper() and len(text) > 10:
        return False  # All caps navigation
    
    # Look for educational keywords
    educational_keywords = [
        "algebra", "calculus", "biology", "chemistry", "physics", "history",
        "literature", "programming", "computer", "science", "mathematics",
        "engineering", "medicine", "law", "business", "economics", "art",
        "music", "language", "philosophy", "psychology", "sociology", "data",
        "statistics", "machine learning", "artificial intelligence", "design",
        "architecture", "geography", "political", "anthropology", "linguistics"
    ]
    
    text_lower = text.lower()
    has_educational_keyword = any(keyword in text_lower for keyword in educational_keywords)
    
    # Or looks like a course/subject name (2-4 words, title case or mixed)
    looks_like_course = (
        2 <= len(words) <= 4 and
        (text[0].isupper() or any(c.isupper() for c in text)) and
        not text.lower().startswith("for ")  # Skip "For X" navigation
    )
    
    return has_educational_keyword or looks_like_course


async def scout_reddit(
    source_name: str,
    source_config: Dict[str, Any],
    existing_domains: Set[str],
    max_domains: int
) -> Dict[str, Any]:
    """
    Scout Reddit for trending domains/topics.
    """
    discovered = []
    
    # Reddit educational subreddits to search
    subreddits = [
        "learnmath", "learnprogramming", "learnpython", "MachineLearning",
        "math", "science", "AskScience", "explainlikeimfive"
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "DomainScoutBot/1.0 (Educational Research)"
            }
            
            for subreddit in subreddits[:2]:  # Limit to 2 subreddits
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"  # Limit to 10 posts
                
                try:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            posts = data.get("data", {}).get("children", [])
                            
                            # Batch posts together to reduce LLM calls
                            post_texts = []
                            for post in posts[:10]:  # Limit to 10 posts
                                post_data = post.get("data", {})
                                title = post_data.get("title", "")
                                selftext = post_data.get("selftext", "")[:500]  # Limit text length
                                if title:
                                    post_texts.append(title)
                            
                            # Combine posts and extract domains in one LLM call with timeout
                            if post_texts:
                                combined_text = "\n".join(post_texts[:10])  # Max 10 posts
                                try:
                                    domains = await asyncio.wait_for(
                                        extract_domains_from_text(
                                            combined_text, 
                                            existing_domains, 
                                            source="reddit"
                                        ),
                                        timeout=20.0  # 20 second timeout per subreddit
                                    )
                                    
                                    for domain_info in domains:
                                        if domain_info["domain_name"] not in [d["domain_name"] for d in discovered]:
                                            discovered.append(domain_info)
                                            if len(discovered) >= max_domains:
                                                break
                                except asyncio.TimeoutError:
                                    logger.warning(f"Reddit domain extraction timed out for {subreddit}")
                                    continue
                                except Exception as e:
                                    logger.warning(f"Error extracting domains from Reddit {subreddit}: {e}")
                                    continue
                        
                        await asyncio.sleep(1)  # Rate limiting
                
                except Exception as e:
                    logger.warning(f"Error fetching Reddit subreddit {subreddit}: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Error scouting Reddit: {e}")
        return {"domains": [], "error": str(e)}
    
    return {
        "domains": discovered[:max_domains],
        "source": source_name,
        "subreddits": subreddits,
        "method": "reddit_api"
    }


async def scout_api_source(
    source_name: str,
    source_config: Dict[str, Any],
    existing_domains: Set[str],
    max_domains: int
) -> Dict[str, Any]:
    """
    Scout a source using its API (if available).
    """
    # Placeholder for API-based scouting
    # Would implement specific API calls for each source
    return {"domains": [], "error": "API method not yet implemented"}


async def extract_domains_from_html(
    html: str,
    source_name: str,
    existing_domains: Set[str]
) -> List[Dict[str, Any]]:
    """
    Extract domain names from HTML using LLM.
    """
    # Clean HTML first - extract text content
    text_content = clean_html_for_extraction(html)
    
    if len(text_content) < 100:
        return []  # Not enough content
    
    # Use LLM to extract educational domain/topic names
    llm = get_llm()
    
    # Create list of existing domains for context (sample)
    existing_sample = list(existing_domains)[:20] if len(existing_domains) > 20 else list(existing_domains)
    
    # Prompt injection defense: treat fetched HTML/text as untrusted data
    safe_text = sanitize_for_llm(text_content[:3000], max_length=3000)
    wrapped_content = wrap_untrusted_content(safe_text, max_length=3000)
    
    prompt = f"""You are analyzing content from {source_name} to identify NEW educational domains/topics that are NOT already in the knowledge graph.

Existing domains (do NOT include these): {', '.join(existing_sample)}

Content from {source_name}:
{wrapped_content}

Extract educational domain names (subjects, topics, courses) that appear in this content.
Focus on:
- Course names
- Subject areas  
- Topic names
- Educational categories
- Emerging fields

For each domain found, provide:
1. Domain name (exact name as it appears)
2. Context (where it was found - e.g., "Course listing", "Subject page")
3. Confidence (0.0-1.0) based on how clearly it's an educational domain

IMPORTANT: Only include domains that are:
- NOT in the existing domains list above
- Specific educational topics (not generic terms)
- Clearly educational in nature

Exclude:
- Generic terms ("Introduction", "Overview", "About")
- Administrative pages ("Contact", "Help", "FAQ")
- Already existing domains

Respond in JSON format:
{{
    "domains": [
        {{
            "domain_name": "Quantum Machine Learning",
            "context": "Course listing page",
            "confidence": 0.9,
            "source": "{source_name}",
            "reason": "Emerging interdisciplinary field combining quantum computing and ML"
        }}
    ]
}}
"""
    
    try:
        response = await llm.ainvoke(prompt)
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        # Parse JSON response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            domains = parsed.get("domains", [])
            
            # Filter out existing domains (double-check)
            new_domains = []
            for d in domains:
                domain_name = d.get("domain_name", "").strip()
                if domain_name and domain_name.lower() not in existing_domains:
                    # Normalize and check again
                    normalized = normalize_domain_name(domain_name)
                    if normalized not in [normalize_domain_name(existing) for existing in existing_domains]:
                        new_domains.append(d)
            
            return new_domains
    
    except Exception as e:
        logger.warning(f"Error extracting domains from HTML: {e}")
    
    return []


def clean_html_for_extraction(html: str) -> str:
    """
    Clean HTML to extract readable text content.
    """
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Extract text from common content containers
    content_patterns = [
        r'<main[^>]*>(.*?)</main>',
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        r'<section[^>]*>(.*?)</section>',
    ]
    
    extracted_text = []
    for pattern in content_patterns:
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        extracted_text.extend(matches)
    
    if not extracted_text:
        # Fallback: extract from body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            extracted_text = [body_match.group(1)]
        else:
            extracted_text = [html]
    
    # Combine and clean
    combined = ' '.join(extracted_text)
    
    # Remove HTML tags
    combined = re.sub(r'<[^>]+>', ' ', combined)
    
    # Clean whitespace
    combined = re.sub(r'\s+', ' ', combined)
    combined = combined.strip()
    
    return combined


async def extract_domains_from_text(
    text: str,
    existing_domains: Set[str],
    source: str = "social_media"
) -> List[Dict[str, Any]]:
    """
    Extract domain names from text using LLM.
    """
    if not text or len(text.strip()) < 50:
        return []
    
    llm = get_llm()
    
    # Sample existing domains for context
    existing_sample = list(existing_domains)[:20] if len(existing_domains) > 20 else list(existing_domains)
    
    # Prompt injection defense: treat retrieved text as untrusted data
    safe_text = sanitize_for_llm(text[:2000], max_length=2000)
    wrapped_content = wrap_untrusted_content(safe_text, max_length=2000)
    
    prompt = f"""Analyze this text from {source} to identify NEW educational domains/topics that people are learning or discussing.

Existing domains (do NOT include): {', '.join(existing_sample)}

Text:
{wrapped_content}

Extract educational domain names (subjects, topics, courses, skills) mentioned that are NOT in the existing list.
Focus on domains that:
- Are specific educational topics
- People are actively learning or asking about
- Are trending or emerging
- Are clearly educational (not just general discussion)

For each NEW domain, provide:
1. Domain name (exact as mentioned)
2. Confidence (0.0-1.0) - higher if clearly educational
3. Reason why it's educational

IMPORTANT: Only include domains that are:
- NOT in the existing domains list
- Clearly educational topics
- Specific enough to be a domain (not too generic)

Respond in JSON:
{{
    "domains": [
        {{
            "domain_name": "LangChain",
            "confidence": 0.90,
            "reason": "Programming framework for LLM applications, actively being learned",
            "context": "Reddit discussion about learning resources"
        }}
    ]
}}
"""
    
    try:
        response = await llm.ainvoke(prompt)
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            domains = parsed.get("domains", [])
            
            # Add source metadata
            for domain in domains:
                domain["source"] = source
                if "context" not in domain:
                    domain["context"] = "Social media discussion"
            
            # Filter existing domains (double-check)
            new_domains = []
            for d in domains:
                domain_name = d.get("domain_name", "").strip()
                if domain_name:
                    # Check against existing
                    normalized = normalize_domain_name(domain_name)
                    is_new = normalized not in [normalize_domain_name(existing) for existing in existing_domains]
                    if is_new:
                        new_domains.append(d)
            
            return new_domains
    
    except Exception as e:
        logger.warning(f"Error extracting domains from text: {e}")
    
    return []


def deduplicate_domains(domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate domains by name, keeping highest confidence version.
    """
    domain_map = {}
    
    for domain in domains:
        name = domain.get("domain_name", "").lower().strip()
        if not name:
            continue
        
        # Normalize name variations
        normalized = normalize_domain_name(name)
        
        if normalized not in domain_map:
            domain_map[normalized] = domain
        else:
            # Keep version with higher confidence
            existing = domain_map[normalized]
            if domain.get("confidence", 0) > existing.get("confidence", 0):
                domain_map[normalized] = domain
    
    return list(domain_map.values())


def normalize_domain_name(name: str) -> str:
    """
    Normalize domain name for comparison.
    """
    # Lowercase, strip, remove extra spaces
    normalized = name.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^(introduction to|basics of|fundamentals of|advanced )', '', normalized)
    normalized = re.sub(r' (course|class|tutorial|guide)$', '', normalized)
    
    return normalized.strip()


async def scout_social_media(
    max_domains: int = 30,
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Scout social media platforms (Reddit, X/Twitter) for trending domains.
    
    Args:
        max_domains: Maximum domains to discover
        min_confidence: Minimum confidence threshold
    
    Returns:
        Dict with discovered domains
    """
    logger.info("Starting social media domain scouting")
    
    existing_domains = get_existing_domains()
    all_discovered = []
    source_results = {}
    
    # Scout social media sources (limit to first 1 to avoid timeout)
    sources_to_scout = list(SCOUT_SOURCES["social_media"].items())[:1]
    for source_name, source_config in sources_to_scout:
        if not source_config.get("enabled", False):
            continue
        
        logger.info(f"Scouting {source_name}...")
        
        try:
            # Add timeout per source
            discovered = await asyncio.wait_for(
                scout_source(
                    source_name=source_name,
                    source_config=source_config,
                    existing_domains=existing_domains,
                    max_domains=max_domains
                ),
                timeout=40.0  # 40 second timeout for social media (Reddit can be slow)
            )
            
            source_results[source_name] = discovered
            all_discovered.extend(discovered.get("domains", []))
            
            logger.info(f"  Found {len(discovered.get('domains', []))} potential new domains from {source_name}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Scouting {source_name} timed out after 40 seconds")
            source_results[source_name] = {
                "domains": [],
                "error": "Timeout after 40 seconds"
            }
        except Exception as e:
            logger.error(f"Error scouting {source_name}: {e}")
            source_results[source_name] = {
                "domains": [],
                "error": str(e)
            }
    
    # Deduplicate and filter
    unique_domains = deduplicate_domains(all_discovered)
    high_confidence = [d for d in unique_domains if d.get("confidence", 0) >= min_confidence]
    high_confidence.sort(key=lambda d: d.get("confidence", 0), reverse=True)
    
    return {
        "discovered_domains": high_confidence[:max_domains],
        "all_discovered": unique_domains,
        "source_results": source_results,
        "statistics": {
            "total_discovered": len(all_discovered),
            "unique_domains": len(unique_domains),
            "high_confidence": len(high_confidence),
            "sources_scouted": len([r for r in source_results.values() if r.get("domains")])
        }
    }


async def full_domain_scout(
    start_with_free: bool = True,
    then_social: bool = True,
    max_domains_per_source: int = 50
) -> Dict[str, Any]:
    """
    Full domain scouting workflow: free sources first, then social media.
    
    Args:
        start_with_free: Scout free educational sources first
        then_social: Then scout social media
        max_domains_per_source: Max domains per source
    
    Returns:
        Complete scouting results
    """
    all_results = {
        "free_educational": None,
        "social_media": None,
        "combined": None
    }
    
    # Step 1: Scout free educational sources
    if start_with_free:
        logger.info("Phase 1: Scouting free educational sources...")
        free_results = await scout_domains_from_free_sources(
            max_domains_per_source=max_domains_per_source
        )
        all_results["free_educational"] = free_results
    
    # Step 2: Scout social media
    if then_social:
        logger.info("Phase 2: Scouting social media...")
        social_results = await scout_social_media(
            max_domains=max_domains_per_source
        )
        all_results["social_media"] = social_results
    
    # Combine results
    all_discovered = []
    if all_results["free_educational"]:
        all_discovered.extend(all_results["free_educational"].get("discovered_domains", []))
    if all_results["social_media"]:
        all_discovered.extend(all_results["social_media"].get("discovered_domains", []))
    
    # Final deduplication
    combined_unique = deduplicate_domains(all_discovered)
    combined_unique.sort(key=lambda d: d.get("confidence", 0), reverse=True)
    
    all_results["combined"] = {
        "discovered_domains": combined_unique,
        "statistics": {
            "total_unique": len(combined_unique),
            "from_free_sources": len(all_results["free_educational"].get("discovered_domains", [])) if all_results["free_educational"] else 0,
            "from_social_media": len(all_results["social_media"].get("discovered_domains", [])) if all_results["social_media"] else 0
        }
    }
    
    return all_results
