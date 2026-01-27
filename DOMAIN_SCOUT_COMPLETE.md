# Domain Scout Agent - Complete Implementation

## ✅ Implementation Complete

The Domain Scout Agent is now fully functional and ready to discover new domains not yet in the knowledge graph.

## Overview

The Domain Scout Agent:
1. **Scrapes free educational sources** first (OpenStax, Khan Academy, MIT OCW, etc.)
2. **Scrapes social media** second (Reddit, X/Twitter)
3. **Compares against existing 287 domains** to find new ones
4. **Ranks by confidence** and returns recommendations

## Workflow

### Phase 1: Free Educational Sources (Priority)

Scouts these platforms:
- **OpenStax** - Free textbooks and subjects
- **Khan Academy** - Courses and topics  
- **MIT OCW** - Open courseware
- **Coursera** - Course categories
- **edX** - Course subjects

**Method:**
1. Fetches HTML from subject/course listing pages
2. Extracts text content (removes scripts, styles, nav)
3. Uses **simple HTML parsing** for common patterns (links, headings)
4. Uses **LLM extraction** for complex content
5. Filters out existing domains
6. Returns new domains with confidence scores

### Phase 2: Social Media (After Free Sources)

Scouts these platforms:
- **Reddit** - Educational subreddits
  - r/learnmath, r/learnprogramming, r/learnpython
  - r/MachineLearning, r/math, r/science
- **X/Twitter** - Trending educational topics
  - (Note: Requires API key for full access)

**Method:**
1. Fetches posts from Reddit API
2. Extracts titles and content
3. Uses **LLM** to identify learning topics
4. Filters existing domains
5. Returns trending/emerging domains

## Usage

### Basic Scouting

```
/scout domains
```

This will:
1. Scout all free educational sources
2. Then scout social media
3. Compare against existing domains
4. Return new domains ranked by confidence

### Scouting Options

```
/scout domains from free sources only
/scout domains from social media only
```

## Domain Extraction Methods

### 1. Simple HTML Parsing

Extracts from:
- **Links** (`<a>` tags) - Common in course listings
- **Headings** (`<h1>`, `<h2>`, `<h3>`) - Section titles
- **List items** - Course/subject lists

**Confidence**: 0.7 (medium)

### 2. LLM Extraction

Uses LLM to:
- Analyze cleaned HTML/text content
- Identify educational domains
- Provide confidence scores
- Filter out generic/administrative terms

**Confidence**: 0.7-0.95 (varies by clarity)

## Confidence Scoring

Each discovered domain gets a confidence score:

| Score | Meaning | Action |
|-------|---------|--------|
| 0.9-1.0 | Very clear educational domain | High priority for integration |
| 0.7-0.9 | Likely educational domain | Review and consider |
| 0.5-0.7 | Possibly educational | Manual review needed |
| <0.5 | Low confidence | May be noise |

## Deduplication

Domains are deduplicated by:
1. **Name normalization**: 
   - Lowercase, strip whitespace
   - Remove common prefixes ("Introduction to", "Basics of")
   - Remove common suffixes ("course", "tutorial")
2. **Confidence**: Keep highest confidence version
3. **Cross-source**: Merge domains from different sources

## Example Output

```
🔍 Domain Scouting Results
============================================================
Existing domains in KG: 287

📚 Free Educational Sources:
   Sources Scouted: 5
   Total Discovered: 45
   Unique New Domains: 32
   High Confidence: 18

   Top New Domains (high confidence):
   1. Quantum Machine Learning (confidence: 0.92, from: openstax)
   2. Prompt Engineering (confidence: 0.88, from: khan_academy)
   3. Ethical AI (confidence: 0.85, from: mit_ocw)
   4. Data Visualization (confidence: 0.82, from: coursera)
   ...

📱 Social Media:
   Sources Scouted: 2
   Total Discovered: 28
   Unique New Domains: 15
   High Confidence: 12

   Top Trending Domains:
   1. LangChain (confidence: 0.90, from: reddit)
   2. Stable Diffusion (confidence: 0.87, from: reddit)
   3. React Server Components (confidence: 0.85, from: reddit)
   ...

📊 Combined Results:
   Total Unique New Domains: 35
   From Free Sources: 18
   From Social Media: 12

   Top 15 Recommended New Domains:
   1. Quantum Machine Learning
      Confidence: 0.92 | Source: openstax
      Context: Course listing page
   2. LangChain
      Confidence: 0.90 | Source: reddit
      Context: Reddit discussion about learning resources
   ...
```

## Integration

Discovered domains can be:
1. **Reviewed**: Check confidence and relevance
2. **Added to taxonomy**: Manually add to `DOMAIN_TAXONOMY`
3. **Categorized**: Assign to appropriate category
4. **Ingested**: Use `/ingest domain <name>` to add to KG

## Files Created

1. **`app/kg/domain_scout.py`** - Core scouting logic
   - `scout_domains_from_free_sources()` - Scout educational platforms
   - `scout_social_media()` - Scout Reddit/X
   - `full_domain_scout()` - Complete workflow
   - `extract_domains_from_html()` - LLM extraction
   - `extract_domains_from_text()` - Text extraction
   - `extract_domains_simple()` - Simple HTML parsing
   - `deduplicate_domains()` - Deduplication
   - `normalize_domain_name()` - Name normalization

2. **`app/graph/domain_scout_worker.py`** - LangGraph worker
   - `domain_scout_node()` - Main worker function
   - Formats and returns results

3. **Updated `app/graph/supervisor.py`**
   - Added `/scout` command
   - Routes to `scout_domains` node

## Configuration

### Enable/Disable Sources

Edit `app/kg/domain_scout.py`:

```python
SCOUT_SOURCES = {
    "free_educational": {
        "openstax": {"enabled": True, "priority": 1},
        "khan_academy": {"enabled": True, "priority": 2},
        "mit_ocw": {"enabled": True, "priority": 3},
        "coursera": {"enabled": True, "priority": 4},
        "edx": {"enabled": True, "priority": 5}
    },
    "social_media": {
        "reddit": {"enabled": True, "priority": 1},
        "twitter": {"enabled": False, "priority": 2}  # Disabled
    }
}
```

### Reddit Subreddits

Edit in `scout_reddit()`:

```python
subreddits = [
    "learnmath", "learnprogramming", "learnpython",
    "MachineLearning", "math", "science", "AskScience"
]
```

## Rate Limiting

- **Reddit API**: 1 second delay between requests
- **Web scraping**: 15-second timeout per page
- **LLM calls**: Sequential to avoid overload

## Error Handling

- **API failures**: Logged but don't stop scouting
- **Timeouts**: Gracefully handled, continue with other sources
- **Parsing errors**: Fallback to simple extraction
- **Network errors**: Continue with other sources

## Next Steps

After discovering new domains:

1. **Review**: Check confidence scores and relevance
2. **Categorize**: Determine which category they belong to
3. **Add to taxonomy**: Update `DOMAIN_TAXONOMY` in `domains.py`
4. **Ingest**: Run `ingest_domains.py` to add to KG
5. **Gather sources**: Use `/gather sources for <new_domain>`

## Testing

Test domain scouting:

```python
import asyncio
from app.kg.domain_scout import scout_domains_from_free_sources

async def test():
    results = await scout_domains_from_free_sources(max_domains_per_source=10)
    print(f"Found {len(results['discovered_domains'])} new domains")
    for domain in results['discovered_domains'][:5]:
        print(f"  {domain['domain_name']} (confidence: {domain['confidence']:.2f})")

asyncio.run(test())
```

## Related Modules

- **`app/kg/domains.py`**: Domain taxonomy and existing domains
- **`app/kg/api_clients.py`**: API clients (for future enhancements)
- **`app/graph/domain_scout_worker.py`**: LangGraph worker node
- **`app/graph/supervisor.py`**: Graph routing

## Ready to Use!

The Domain Scout Agent is ready to discover new domains. Try:

```
/scout domains
```

It will automatically:
1. ✅ Scout free educational sources first
2. ✅ Then scout social media
3. ✅ Compare against existing 287 domains
4. ✅ Return new domains ranked by confidence
