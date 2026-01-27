# Domain Scout Agent

## Overview

The Domain Scout Agent discovers new educational domains that are **not yet in the knowledge graph** by scraping free educational sources and social media platforms.

## Workflow

### Phase 1: Free Educational Sources (First Priority)

Scouts these free sources to identify domains:
1. **OpenStax** - Free textbooks and subjects
2. **Khan Academy** - Courses and topics
3. **MIT OCW** - Open courseware subjects
4. **Coursera** - Course categories
5. **edX** - Course subjects

### Phase 2: Social Media (After Free Sources)

Scouts social platforms for trending/emerging domains:
1. **Reddit** - Educational subreddits (r/learnmath, r/learnprogramming, etc.)
2. **X/Twitter** - Trending educational topics (requires API key for full access)

## How It Works

1. **Scrapes HTML/APIs** from educational platforms
2. **Uses LLM** to extract domain names from content
3. **Compares** against existing domain taxonomy
4. **Filters** to find truly new domains
5. **Ranks** by confidence score
6. **Returns** new domains with metadata

## Usage

### Basic Scouting

```
/scout domains
```

This will:
1. Scout free educational sources first
2. Then scout social media
3. Compare against existing 287 domains
4. Return new domains with confidence scores

### Scouting Options

```
/scout domains from free sources only
/scout domains from social media only
```

## Output Format

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
   1. Quantum Computing (confidence: 0.92, from: openstax)
   2. Data Visualization (confidence: 0.88, from: khan_academy)
   3. Ethical AI (confidence: 0.85, from: mit_ocw)
   ...

📱 Social Media:
   Sources Scouted: 2
   Total Discovered: 28
   Unique New Domains: 15
   High Confidence: 12

   Top Trending Domains:
   1. LangChain (confidence: 0.90, from: reddit)
   2. Stable Diffusion (confidence: 0.87, from: reddit)
   ...

📊 Combined Results:
   Total Unique New Domains: 35
   From Free Sources: 18
   From Social Media: 12

   Top 15 Recommended New Domains:
   1. Quantum Computing
      Confidence: 0.92 | Source: openstax
      Context: Course listing page
   ...
```

## Domain Extraction Process

### From HTML (Educational Platforms)

1. Fetches HTML from platform pages
2. Sends to LLM with prompt to extract educational domains
3. LLM identifies:
   - Course names
   - Subject areas
   - Topic names
   - Educational categories
4. Filters out:
   - Generic terms ("Introduction", "Overview")
   - Administrative pages ("About", "Contact")
   - Already existing domains

### From Text (Social Media)

1. Fetches posts from Reddit/X
2. Extracts titles and content
3. Uses LLM to identify:
   - Learning topics
   - Trending subjects
   - Emerging domains
4. Filters existing domains

## Confidence Scoring

Each discovered domain gets a confidence score (0.0-1.0):
- **0.9-1.0**: Very clear educational domain
- **0.7-0.9**: Likely educational domain
- **0.5-0.7**: Possibly educational domain
- **<0.5**: Low confidence, may be noise

## Deduplication

Domains are deduplicated by:
1. **Name normalization**: Lowercase, strip, remove common prefixes
2. **Confidence**: Keep highest confidence version
3. **Cross-source**: Merge domains from different sources

## Integration with Knowledge Graph

Discovered domains can be:
1. **Reviewed**: Check confidence and relevance
2. **Added to taxonomy**: Use `/ingest domain <name>` to add
3. **Categorized**: Assign to appropriate category
4. **Linked**: Connect to related domains

## Configuration

### Enable/Disable Sources

Edit `app/kg/domain_scout.py`:

```python
SCOUT_SOURCES = {
    "free_educational": {
        "openstax": {"enabled": True, "priority": 1},
        "khan_academy": {"enabled": True, "priority": 2},
        ...
    },
    "social_media": {
        "reddit": {"enabled": True, "priority": 1},
        "twitter": {"enabled": False, "priority": 2},  # Disabled
        ...
    }
}
```

### Reddit Subreddits

Edit subreddit list in `scout_reddit()`:

```python
subreddits = [
    "learnmath", "learnprogramming", "learnpython",
    "MachineLearning", "math", "science", ...
]
```

## Rate Limiting

The system includes rate limiting:
- **Reddit**: 1 second delay between requests
- **Web scraping**: 15-second timeout per page
- **LLM calls**: Sequential to avoid overload

## Error Handling

- **API failures**: Logged but don't stop scouting
- **Timeouts**: Gracefully handled
- **Parsing errors**: Default to empty results
- **Network errors**: Continue with other sources

## Example: Discovering New Domains

### Scenario: AI/ML Domain Expansion

```
/scout domains
```

**Discovers:**
- "LangChain" (from Reddit, confidence: 0.90)
- "Stable Diffusion" (from Reddit, confidence: 0.87)
- "Transformer Architecture" (from OpenStax, confidence: 0.85)
- "Prompt Engineering" (from Reddit, confidence: 0.82)

**Result**: 4 new high-confidence domains to potentially add to taxonomy

## Future Enhancements

1. **More Sources**: Add more educational platforms
2. **Trending Detection**: Identify rapidly growing domains
3. **Domain Validation**: Verify domains are educational
4. **Auto-categorization**: Automatically assign categories
5. **Bulk Integration**: Add multiple domains at once
6. **Periodic Scouting**: Schedule regular domain discovery

## Related Modules

- **`app/kg/domain_scout.py`**: Core scouting logic
- **`app/graph/domain_scout_worker.py`**: LangGraph worker node
- **`app/kg/domains.py`**: Domain taxonomy and existing domains
- **`app/kg/api_clients.py`**: API clients for web scraping

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
