# Real Source Discovery Implementation

## Overview

The source discovery system now uses **real API calls** to gather sources from the internet. Sources are automatically ranked by **validity (quality) and cost**, prioritizing high-confidence free sources first.

## Priority Ranking Formula

Sources are ranked using:

```
Priority = (Quality × 0.7) - (Cost × 0.3) + (Free Bonus: +0.1 if cost = 0)
```

**Ranking Order:**
1. **High confidence & free** (Priority: 0.7-0.9)
2. **High confidence & low cost** (Priority: 0.5-0.7)
3. **Medium confidence & free** (Priority: 0.4-0.6)
4. **Low confidence & costly** (Priority: 0.0-0.3)

## Real API Integrations

### Academic Sources

1. **Semantic Scholar** (`search_semantic_scholar`)
   - API: `https://api.semanticscholar.org/graph/v1/paper/search`
   - Returns: Academic papers with citations, DOIs, abstracts
   - Cost: **FREE**
   - Rate Limit: 100 requests per 5 minutes

2. **arXiv** (`search_arxiv`)
   - API: `http://export.arxiv.org/api/query`
   - Returns: Preprints and research papers
   - Cost: **FREE**
   - Rate Limit: 1 request per 3 seconds

3. **OpenAlex** (`search_openalex`)
   - API: `https://api.openalex.org/works`
   - Returns: Academic works with metadata
   - Cost: **FREE**
   - Rate Limit: Very high (100,000 per day)

### Educational Sources

1. **OpenStax** (`search_openstax`)
   - Method: URL construction (no public API)
   - Returns: Free textbook links
   - Cost: **FREE**

2. **Khan Academy** (`search_khan_academy`)
   - Method: Topic mapping and URL construction
   - Returns: Course and topic links
   - Cost: **FREE**

3. **MIT OCW** (`search_mit_ocw`)
   - Method: Subject mapping and URL construction
   - Returns: Course links
   - Cost: **FREE**

### General Sources

1. **Wikipedia** (`search_wikipedia`)
   - API: `https://en.wikipedia.org/api/rest_v1/page/search`
   - Returns: Encyclopedia articles
   - Cost: **FREE**

## Cost Detection

The system automatically detects cost:

| Source Type | Cost Score | Examples |
|------------|------------|----------|
| Free | 0.0 | OpenStax, Khan Academy, MIT OCW, arXiv, Wikipedia |
| Low | 0.1-0.2 | Textbooks (may require purchase), Educational platforms |
| Medium | 0.4-0.5 | Journal subscriptions, Premium courses |
| High | 0.7-0.9 | Paywalled papers, Proprietary content |

Detection methods:
1. **URL domain check**: `.edu`, `.gov`, `openstax.org`, etc. = free
2. **Source type**: `openstax`, `khan_academy`, `arxiv` = free
3. **Paywall keywords**: `paywall`, `subscription`, `purchase` = high cost

## Usage

### Step 1: Discover Sources

```
/gather sources for Algebra
```

This will:
1. Call real APIs (Semantic Scholar, arXiv, OpenAlex, Wikipedia, etc.)
2. Evaluate quality for each source
3. Calculate cost for each source
4. Rank by priority (high quality & free first)
5. Return top sources

### Step 2: Fetch Content

```
/fetch content for Algebra
```

This will:
1. Take discovered sources (already ranked by priority)
2. Fetch actual content from URLs
3. Start with highest priority sources (free + high quality)
4. Continue until max_sources or min_priority reached
5. Return fetched content ready for extraction

## Example Output

```
📚 Source Discovery Results
============================================================

🔍 Domain: Algebra
   Category: mathematics
   Difficulty: intermediate

   Found 15 high-quality sources (quality ≥ 0.65)
   Average Quality: 0.782
   Average Priority: 0.612
   Free Sources: 12 | Paid: 3
   Source Types: textbook, academic_paper, educational_platform, encyclopedia

   Top Sources (ranked by priority - high quality & free first):
   1. OpenStax Algebra Textbook (textbook, 2022)
      Quality: 0.950 | Cost: FREE | Priority: 0.775
   2. Khan Academy: Algebra (educational_platform, 2024)
      Quality: 0.800 | Cost: FREE | Priority: 0.660
   3. Research on Algebraic Structures (academic_paper, 2023)
      Quality: 0.876 | Cost: $LOW | Priority: 0.613
   ...
```

## API Rate Limiting

The system includes rate limiting:
- **Semantic Scholar**: 0.5s delay between requests
- **arXiv**: 1.0s delay (1 req per 3 sec limit)
- **OpenAlex**: 0.2s delay
- **Concurrent fetches**: Max 5 parallel requests

## Error Handling

- **API failures**: Logged but don't stop discovery
- **Timeouts**: 10-second timeout per request
- **Network errors**: Gracefully handled
- **Missing data**: Defaults provided for missing fields

## Content Fetching

After discovery, content is fetched:
- **Priority order**: High priority sources first
- **Parallel fetching**: Up to 5 concurrent requests
- **Content extraction**: HTML to text conversion
- **Length limiting**: 10,000 characters per source

## Installation

For real API calls, ensure `aiohttp` is installed:

```bash
pip install aiohttp
```

## Testing

Test with a real domain:

```python
from app.kg.source_discovery import discover_sources_for_domain

result = await discover_sources_for_domain("Algebra", max_sources=10)
print(f"Found {len(result['sources'])} sources")
for source in result['sources'][:5]:
    print(f"  {source['properties']['title']} - Priority: {source.get('priority_score', 0):.3f}")
```

## Future Enhancements

1. **Caching**: Cache API responses to avoid redundant calls
2. **More APIs**: Add Crossref, PubMed, Google Scholar
3. **Web Scraping**: For sources without APIs (OpenStax, Khan Academy)
4. **Content Validation**: Verify fetched content relevance
5. **Incremental Fetching**: Resume from last fetched source

## Related Modules

- **`app/kg/api_clients.py`**: Real API client implementations
- **`app/kg/source_discovery.py`**: Discovery orchestration
- **`app/kg/source_fetcher.py`**: Content fetching and priority ranking
- **`app/kg/scoring.py`**: Quality and confidence formulas
- **`app/graph/source_gatherer.py`**: Source gathering worker
- **`app/graph/content_fetcher.py`**: Content fetching worker
