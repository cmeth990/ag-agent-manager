"""
API Clients for Real Source Discovery
Implements actual API calls to source providers.
"""
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional
from urllib.parse import quote, urlencode
import json
from app.retry import with_retry
from app.queue.rate_limiter import check_rate_limit, record_request

logger = logging.getLogger(__name__)


@with_retry(max_retries=2, backoff_base=2.0, operation_name="search_semantic_scholar")
async def search_semantic_scholar(query: str, limit: int = 10, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search Semantic Scholar API for academic papers.
    
    API: https://api.semanticscholar.org/graph/v1/paper/search
    """
    # Rate limiting: check before making request
    allowed, reason = check_rate_limit("semantic_scholar", domain=domain)
    if not allowed:
        logger.warning(f"Rate limited: {reason}")
        return []  # Return empty instead of failing
    
    sources = []
    
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": min(limit, 100),  # API limit
            "fields": "title,authors,year,abstract,url,doi,citationCount,venue"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    papers = data.get("data", [])
                    
                    for paper in papers[:limit]:
                        # Extract authors
                        authors = [f"{a.get('name', '')}" for a in paper.get("authors", [])]
                        
                        source = {
                            "id": f"SRC:s2_{paper.get('paperId', 'unknown')}",
                            "label": "Source",
                            "properties": {
                                "title": paper.get("title", "Untitled"),
                                "authors": authors,
                                "year": paper.get("year"),
                                "type": "academic_paper",
                                "doi": paper.get("doi"),
                                "url": paper.get("url"),
                                "trustScore": 0.85,
                                "citationCount": paper.get("citationCount", 0),
                                "peerReviewed": True,
                                "venue": paper.get("venue", ""),
                                "abstract": paper.get("abstract", "")
                            }
                        }
                        sources.append(source)
                    
                    logger.info(f"Semantic Scholar: Found {len(sources)} papers for '{query}'")
                    # Record successful request for rate limiting
                    record_request("semantic_scholar", domain=domain)
                else:
                    logger.warning(f"Semantic Scholar API returned status {response.status}")
                    # Still record request (failed but counted)
                    record_request("semantic_scholar", domain=domain)
    
    except Exception as e:
        logger.error(f"Error searching Semantic Scholar: {e}")
        # Record failed request
        record_request("semantic_scholar", domain=domain)
    
    return sources


@with_retry(max_retries=2, backoff_base=2.0, operation_name="search_arxiv")
async def search_arxiv(query: str, limit: int = 10, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search arXiv API for preprints.
    
    API: http://export.arxiv.org/api/query
    """
    # Rate limiting
    allowed, reason = check_rate_limit("arxiv", domain=domain)
    if not allowed:
        logger.warning(f"Rate limited: {reason}")
        return []
    
    sources = []
    
    try:
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(limit, 100),
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse Atom XML (simplified - use proper XML parser in production)
                    import re
                    entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL)
                    
                    for entry in entries[:limit]:
                        # Extract title
                        title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                        title = title_match.group(1).strip() if title_match else "Untitled"
                        title = re.sub(r'\s+', ' ', title)  # Clean whitespace
                        
                        # Extract authors
                        authors = re.findall(r'<name>(.*?)</name>', entry)
                        
                        # Extract year
                        published_match = re.search(r'<published>(\d{4})', entry)
                        year = int(published_match.group(1)) if published_match else None
                        
                        # Extract ID
                        id_match = re.search(r'<id>(.*?)</id>', entry)
                        arxiv_id = id_match.group(1).split('/')[-1] if id_match else None
                        
                        if arxiv_id:
                            source = {
                                "id": f"SRC:arxiv_{arxiv_id}",
                                "label": "Source",
                                "properties": {
                                    "title": title,
                                    "authors": authors,
                                    "year": year,
                                    "type": "preprint",
                                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                                    "trustScore": 0.70,
                                    "peerReviewed": False,
                                    "arxiv_id": arxiv_id
                                }
                            }
                            sources.append(source)
                    
                    logger.info(f"arXiv: Found {len(sources)} preprints for '{query}'")
                    record_request("arxiv", domain=domain)
                else:
                    logger.warning(f"arXiv API returned status {response.status}")
                    record_request("arxiv", domain=domain)
    
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
        record_request("arxiv", domain=domain)
    
    return sources


@with_retry(max_retries=2, backoff_base=2.0, operation_name="search_openalex")
async def search_openalex(query: str, limit: int = 10, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search OpenAlex API for academic works.
    
    API: https://api.openalex.org/works
    """
    # Rate limiting
    allowed, reason = check_rate_limit("openalex", domain=domain)
    if not allowed:
        logger.warning(f"Rate limited: {reason}")
        return []
    
    sources = []
    
    try:
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "per_page": min(limit, 200),
            "sort": "relevance_score:desc"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    works = data.get("results", [])
                    
                    for work in works[:limit]:
                        # Extract authors
                        authors = []
                        for author in work.get("authorships", [])[:5]:  # Limit to 5 authors
                            author_name = author.get("author", {}).get("display_name", "")
                            if author_name:
                                authors.append(author_name)
                        
                        # Get primary location
                        primary_location = work.get("primary_location", {})
                        source_url = primary_location.get("landing_page_url") or primary_location.get("pdf_url")
                        
                        source = {
                            "id": f"SRC:oa_{work.get('id', '').split('/')[-1]}",
                            "label": "Source",
                            "properties": {
                                "title": work.get("title", "Untitled"),
                                "authors": authors,
                                "year": work.get("publication_date", "")[:4] if work.get("publication_date") else None,
                                "type": "academic_paper",
                                "doi": work.get("doi", "").replace("https://doi.org/", "") if work.get("doi") else None,
                                "url": source_url,
                                "trustScore": 0.80,
                                "citationCount": work.get("cited_by_count", 0),
                                "peerReviewed": work.get("type") == "article",
                                "openalex_id": work.get("id", "")
                            }
                        }
                        sources.append(source)
                    
                    logger.info(f"OpenAlex: Found {len(sources)} works for '{query}'")
                    record_request("openalex", domain=domain)
                else:
                    logger.warning(f"OpenAlex API returned status {response.status}")
                    record_request("openalex", domain=domain)
    
    except Exception as e:
        logger.error(f"Error searching OpenAlex: {e}")
        record_request("openalex", domain=domain)
    
    return sources


@with_retry(max_retries=2, backoff_base=2.0, operation_name="search_wikipedia")
async def search_wikipedia(query: str, limit: int = 5, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search Wikipedia for articles.
    
    API: https://en.wikipedia.org/api/rest_v1/page/summary/{title}
    """
    # Rate limiting
    allowed, reason = check_rate_limit("wikipedia", domain=domain)
    if not allowed:
        logger.warning(f"Rate limited: {reason}")
        return []
    
    sources = []
    
    try:
        # First, search for matching pages
        search_url = "https://en.wikipedia.org/api/rest_v1/page/search"
        params = {"q": query, "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    pages = data.get("pages", [])
                    
                    for page in pages[:limit]:
                        title = page.get("title", "")
                        key = page.get("key", "")
                        
                        if key:
                            # Get full page summary
                            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(key)}"
                            
                            try:
                                async with session.get(summary_url, timeout=aiohttp.ClientTimeout(total=5)) as summary_resp:
                                    if summary_resp.status == 200:
                                        summary_data = await summary_resp.json()
                                        
                                        source = {
                                            "id": f"SRC:wiki_{key.replace(' ', '_')}",
                                            "label": "Source",
                                            "properties": {
                                                "title": title,
                                                "type": "encyclopedia",
                                                "url": summary_data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                                                "trustScore": 0.70,
                                                "year": 2024,  # Wikipedia is always current
                                                "description": summary_data.get("extract", "")
                                            }
                                        }
                                        sources.append(source)
                            except:
                                pass  # Skip if summary fetch fails
                    
                    logger.info(f"Wikipedia: Found {len(sources)} articles for '{query}'")
                    record_request("wikipedia", domain=domain)
    
    except Exception as e:
        logger.error(f"Error searching Wikipedia: {e}")
        record_request("wikipedia", domain=domain)
    
    return sources


async def search_openstax(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search OpenStax for free textbooks.
    
    Note: OpenStax doesn't have a public API, so we search their website.
    """
    sources = []
    
    try:
        # OpenStax book search (simplified - would need web scraping in production)
        # For now, return known OpenStax books that match the query
        openstax_books = {
            "algebra": "https://openstax.org/details/books/algebra-and-trigonometry",
            "calculus": "https://openstax.org/details/books/calculus-volume-1",
            "biology": "https://openstax.org/details/books/biology-2e",
            "chemistry": "https://openstax.org/details/books/chemistry-2e",
            "physics": "https://openstax.org/details/books/university-physics-volume-1",
        }
        
        query_lower = query.lower()
        for subject, url in openstax_books.items():
            if subject in query_lower:
                source = {
                    "id": f"SRC:openstax_{subject}",
                    "label": "Source",
                    "properties": {
                        "title": f"OpenStax {subject.title()} Textbook",
                        "type": "textbook",
                        "url": url,
                        "trustScore": 0.95,
                        "year": 2022,
                        "peerReviewed": True,
                        "authors": ["OpenStax Contributors"]
                    }
                }
                sources.append(source)
                if len(sources) >= limit:
                    break
        
        logger.info(f"OpenStax: Found {len(sources)} books for '{query}'")
    
    except Exception as e:
        logger.error(f"Error searching OpenStax: {e}")
    
    return sources


async def search_khan_academy(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search Khan Academy for educational content.
    
    Note: Khan Academy API is limited, so we construct URLs based on query.
    """
    sources = []
    
    try:
        # Khan Academy topic mapping (simplified)
        khan_topics = {
            "algebra": "algebra-basics",
            "calculus": "calculus-1",
            "geometry": "geometry",
            "biology": "biology",
            "chemistry": "chemistry",
            "physics": "physics",
        }
        
        query_lower = query.lower()
        for subject, topic in khan_topics.items():
            if subject in query_lower:
                source = {
                    "id": f"SRC:khan_{topic}",
                    "label": "Source",
                    "properties": {
                        "title": f"Khan Academy: {subject.title()}",
                        "type": "educational_platform",
                        "url": f"https://www.khanacademy.org/{topic}",
                        "trustScore": 0.80,
                        "year": 2024
                    }
                }
                sources.append(source)
                if len(sources) >= limit:
                    break
        
        logger.info(f"Khan Academy: Found {len(sources)} courses for '{query}'")
    
    except Exception as e:
        logger.error(f"Error searching Khan Academy: {e}")
    
    return sources


async def search_mit_ocw(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search MIT OpenCourseWare for courses.
    
    Note: MIT OCW doesn't have a public API, so we construct URLs.
    """
    sources = []
    
    try:
        # MIT OCW subject mapping
        mit_subjects = {
            "mathematics": "mathematics",
            "algebra": "mathematics",
            "calculus": "mathematics",
            "physics": "physics",
            "biology": "biology",
            "chemistry": "chemistry",
        }
        
        query_lower = query.lower()
        for subject, mit_subject in mit_subjects.items():
            if subject in query_lower:
                source = {
                    "id": f"SRC:mitocw_{mit_subject}",
                    "label": "Source",
                    "properties": {
                        "title": f"MIT OCW: {subject.title()}",
                        "type": "university_course",
                        "url": f"https://ocw.mit.edu/courses/{mit_subject}",
                        "trustScore": 0.90,
                        "year": 2023
                    }
                }
                sources.append(source)
                if len(sources) >= limit:
                    break
        
        logger.info(f"MIT OCW: Found {len(sources)} courses for '{query}'")
    
    except Exception as e:
        logger.error(f"Error searching MIT OCW: {e}")
    
    return sources
