# Source Gathering Agent

## Overview

The Source Gathering Agent discovers and evaluates high-quality sources for educational domains. It integrates with the knowledge graph to find academic papers, textbooks, courses, and other educational resources.

## Features

1. **Domain-Aware Discovery**: Searches for sources specific to each domain
2. **Quality Scoring**: Uses the source quality formula to evaluate each source
3. **Multi-Provider Search**: Searches academic, educational, and general sources
4. **Automatic Filtering**: Only returns sources that meet domain quality thresholds
5. **Recommendations**: Provides actionable recommendations for improvement

## Usage

### Basic Command

```
/gather sources for <domain>
```

Examples:
- `/gather sources for Algebra`
- `/gather sources for Machine Learning`
- `/gather sources for Quantum Mechanics`

### Multiple Domains

```
/gather sources for Algebra and Geometry
```

### Category-Wide Discovery

```
/gather sources for all mathematics domains
```

## Architecture

### Components

1. **`source_gatherer_node`** (`app/graph/source_gatherer.py`)
   - Main worker node for source gathering
   - Extracts domain(s) from user input
   - Coordinates source discovery
   - Formats and returns results

2. **`source_discovery`** (`app/kg/source_discovery.py`)
   - Core discovery logic
   - Multi-provider search coordination
   - Quality evaluation integration
   - Statistics and recommendations

### Source Providers

#### Academic Sources
- **Semantic Scholar**: Academic papers and citations
- **arXiv**: Preprints and research papers
- **OpenAlex**: Open academic metadata
- **Crossref**: DOI-based academic references

#### Educational Sources
- **OpenStax**: Free textbooks
- **Khan Academy**: Educational videos and courses
- **MIT OCW**: Open courseware
- **LibreTexts**: Open educational resources

#### General Sources
- **Web Search**: General web content
- **Wikipedia**: Encyclopedia articles

## Source Quality Evaluation

Each discovered source is evaluated using the source quality formula:

```
Q_source = (Q_type × 25%) + (Q_credibility × 25%) + (Q_relevance × 20%) + 
           (Q_recency × 15%) + (Q_impact × 10%) + (Q_verification × 5%)
```

Sources must meet the domain's quality threshold to be included:
- **Advanced domains**: Min quality 0.75
- **Intermediate domains**: Min quality 0.65
- **Beginner domains**: Min quality 0.55

## Output Format

The agent returns:

1. **Source List**: Ranked by quality score
2. **Statistics**: 
   - Total sources discovered
   - Sources meeting quality threshold
   - Average quality score
   - Source type distribution
3. **Recommendations**: Suggestions for improvement

### Example Output

```
📚 Source Discovery Results
============================================================

🔍 Domain: Algebra
   Category: mathematics
   Difficulty: intermediate

   Found 15 high-quality sources (quality ≥ 0.65)
   Average Quality: 0.782
   Source Types: textbook, academic_paper, educational_platform

   Top Sources:
   1. OpenStax Algebra Textbook (textbook, 2022) - Quality: 0.950
   2. Research on Algebraic Structures (academic_paper, 2023) - Quality: 0.876
   3. Khan Academy: Algebra (educational_platform, 2024) - Quality: 0.800
   ...

   ⚠️  Recommendations:
      • Low source diversity. Seek different source types.

============================================================

📊 Summary:
   Total Domains: 1
   Total Sources: 15
   Average Quality: 0.782
```

## Integration with Knowledge Graph

Discovered sources can be:
1. **Stored in KG**: Added as Source nodes
2. **Linked to Domains**: Connected via NESTED_IN edges
3. **Used for Claims**: Referenced when extracting claims

## Future Enhancements

1. **Real API Integration**: Connect to actual source provider APIs
2. **Caching**: Cache discovered sources to avoid redundant searches
3. **Batch Discovery**: Gather sources for multiple domains in parallel
4. **Source Validation**: Verify source accessibility and content
5. **Automatic Ingestion**: Option to automatically add sources to KG

## Configuration

Source providers can be enabled/disabled in `app/kg/source_discovery.py`:

```python
SOURCE_PROVIDERS = {
    "academic": {
        "semantic_scholar": {"enabled": True, "priority": 1},
        "arxiv": {"enabled": True, "priority": 2},
        ...
    },
    ...
}
```

## API Integration (TODO)

To enable real source discovery, implement API clients:

1. **Semantic Scholar API**:
   ```python
   GET https://api.semanticscholar.org/graph/v1/paper/search?query={query}
   ```

2. **arXiv API**:
   ```python
   GET http://export.arxiv.org/api/query?search_query=all:{query}
   ```

3. **OpenStax API**:
   ```python
   GET https://openstax.org/api/v2/books?q={query}
   ```

4. **Khan Academy API**:
   ```python
   GET https://www.khanacademy.org/api/v1/topic/{topic}/exercises
   ```

## Testing

Test the source gatherer:

```python
from app.graph.source_gatherer import source_gatherer_node
from app.graph.state import AgentState

state = AgentState(
    user_input="gather sources for Algebra",
    intent="gather_sources"
)

result = await source_gatherer_node(state)
print(result["final_response"])
```

## Related Modules

- **`app/kg/scoring.py`**: Source quality and claim confidence formulas
- **`app/kg/domains.py`**: Domain taxonomy and metadata
- **`app/graph/workers.py`**: Other worker nodes (extractor, linker, writer)
