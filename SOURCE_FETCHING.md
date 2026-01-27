# Source Fetching and Content Gathering

## Overview

The source fetching system gathers actual content from discovered sources, prioritizing high-confidence free sources over low-confidence costly ones.

## Priority Ranking Formula

Sources are ranked using a combined priority score:

```
Priority = (Quality × 0.7) - (Cost × 0.3) + (Free Bonus: +0.1 if cost = 0)
```

**Higher priority = better** (high quality, low cost)

### Components

1. **Quality Score** (70% weight): From source quality formula
   - Type, credibility, relevance, recency, impact, verification

2. **Cost Score** (30% weight): Cost tier (0.0 = free, 1.0 = very expensive)
   - Free: 0.0 (OpenStax, Khan Academy, MIT OCW, arXiv, etc.)
   - Low: 0.1-0.2 (textbooks, educational platforms)
   - Medium: 0.4-0.5 (subscriptions, premium courses)
   - High: 0.7-0.9 (paywalled papers, proprietary content)

3. **Free Bonus**: +0.1 boost for completely free sources

## Cost Detection

The system automatically detects cost based on:

1. **URL Domain**: Checks for known free domains
   - `.edu`, `.gov`, `openstax.org`, `khanacademy.org`, `ocw.mit.edu`, etc.

2. **Source Type**: Categorizes by type
   - Free: `openstax`, `khan_academy`, `mit_ocw`, `arxiv`, `oer`
   - Low: `textbook`, `educational_platform`
   - Medium: `subscription`, `premium_course`
   - High: `paywalled_paper`, `proprietary_textbook`

3. **Paywall Indicators**: Detects paywall keywords in URL
   - `paywall`, `subscription`, `purchase`, `buy`, `premium`

## Workflow

### Step 1: Discover Sources

```
/gather sources for <domain>
```

Discovers sources and ranks them by priority:
- High confidence & free sources first
- Low confidence & costly sources last

### Step 2: Fetch Content

```
/fetch content for <domain>
```

Fetches actual content from sources in priority order:
1. Starts with highest priority (free + high quality)
2. Continues until reaching max_sources or min_priority threshold
3. Fetches content in parallel (max 5 concurrent)

## Usage Examples

### Basic Discovery and Fetching

```
/gather sources for Algebra
```

Output shows sources ranked by priority:
```
Top Sources (ranked by priority - high quality & free first):
1. OpenStax Algebra Textbook (textbook, 2022)
   Quality: 0.950 | Cost: FREE | Priority: 0.775
2. Research on Algebraic Structures (academic_paper, 2023)
   Quality: 0.876 | Cost: $LOW | Priority: 0.613
...
```

### Fetch Content

```
/fetch content for Algebra
```

Fetches actual content from top sources:
```
Fetched Sources (priority order):
1. ✅ OpenStax Algebra Textbook
   Quality: 0.950 | Cost: FREE | Priority: 0.775
   Content preview: Algebra is a branch of mathematics...
2. ✅ Research on Algebraic Structures
   Quality: 0.876 | Cost: $LOW | Priority: 0.613
   Content preview: This paper explores...
```

## Content Fetching

### Features

1. **Priority-Based**: Fetches high priority sources first
2. **Parallel Fetching**: Up to 5 concurrent requests
3. **Error Handling**: Gracefully handles timeouts and errors
4. **Content Extraction**: Extracts text from HTML
5. **Length Limiting**: Truncates very long content (10,000 chars default)

### Fetch Statistics

After fetching, you get:
- Successfully fetched count
- Failed fetch count
- Free vs paid source breakdown
- Total content length
- Average quality and priority

## Cost Tiers

| Tier | Cost Score | Examples |
|------|------------|----------|
| Free | 0.0 | OpenStax, Khan Academy, MIT OCW, arXiv, Wikipedia |
| Low | 0.1-0.2 | Textbooks (may require purchase), Educational platforms |
| Medium | 0.4-0.5 | Journal subscriptions, Premium courses |
| High | 0.7-0.9 | Paywalled papers, Proprietary textbooks |

## Priority Examples

### High Priority (Free + High Quality)
- OpenStax textbook (Quality: 0.95, Cost: 0.0) → Priority: 0.775
- MIT OCW course (Quality: 0.90, Cost: 0.0) → Priority: 0.730

### Medium Priority (Free + Medium Quality)
- Wikipedia article (Quality: 0.70, Cost: 0.0) → Priority: 0.590
- arXiv preprint (Quality: 0.70, Cost: 0.0) → Priority: 0.590

### Lower Priority (Paid + High Quality)
- Academic paper (Quality: 0.90, Cost: 0.2) → Priority: 0.570
- Textbook (Quality: 0.95, Cost: 0.2) → Priority: 0.605

### Low Priority (Paid + Low Quality)
- Paywalled paper (Quality: 0.60, Cost: 0.8) → Priority: 0.180
- Proprietary content (Quality: 0.50, Cost: 0.9) → Priority: 0.080

## Integration with Knowledge Graph

Fetched content can be:
1. **Stored as Source nodes**: With fetched content in properties
2. **Used for extraction**: Content fed to extractor for concept/claim extraction
3. **Linked to domains**: Sources linked to domain nodes

## Configuration

### Fetch Parameters

```python
await gather_domain_content_prioritized(
    sources=sources,
    domain_name="Algebra",
    max_sources=10,        # Max sources to fetch
    min_priority=0.0       # Minimum priority threshold
)
```

### Concurrency

Default: 5 concurrent requests
- Adjustable via `asyncio.Semaphore(5)` in `source_fetcher.py`

### Timeout

Default: 10 seconds per request
- Adjustable via `aiohttp.ClientTimeout(total=10)`

## Error Handling

The system handles:
- **Timeouts**: 10-second timeout per request
- **HTTP Errors**: Non-200 status codes
- **Network Errors**: Connection failures
- **Parsing Errors**: Invalid HTML/content

Failed sources are logged but don't stop the process.

## Recommendations

The system provides recommendations:
- "Consider prioritizing more free sources for cost efficiency"
- "Average source quality is below optimal"
- "Many sources failed to fetch. Check URLs and accessibility"

## Future Enhancements

1. **Caching**: Cache fetched content to avoid re-fetching
2. **Incremental Fetching**: Resume from last fetched source
3. **Content Validation**: Verify content relevance to domain
4. **Extraction Integration**: Automatically extract concepts from fetched content
5. **Rate Limiting**: Respect API rate limits for different providers

## Related Modules

- **`app/kg/source_discovery.py`**: Source discovery
- **`app/kg/source_fetcher.py`**: Content fetching and priority ranking
- **`app/kg/scoring.py`**: Source quality scoring
- **`app/graph/source_gatherer.py`**: Source gathering worker
- **`app/graph/content_fetcher.py`**: Content fetching worker
