"""
Context compression: chunk documents, retrieve relevant chunks, domain briefs.
Reduces token usage by only sending relevant context to LLMs.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.cost.cache import get_cache

logger = logging.getLogger(__name__)

# Default chunk size (characters)
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_CHUNK_OVERLAP = 200


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk (characters)
        overlap: Overlap between chunks (characters)
    
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Move start forward (with overlap)
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def retrieve_relevant_chunks(
    query: str,
    chunks: List[str],
    top_k: int = 3,
) -> List[str]:
    """
    Retrieve most relevant chunks for a query.
    
    Simple implementation: keyword matching.
    Can be enhanced with embeddings/semantic search.
    
    Args:
        query: Query string
        chunks: List of text chunks
        top_k: Number of chunks to return
    
    Returns:
        Top-k most relevant chunks
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Score chunks by keyword overlap
    scored = []
    for i, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        chunk_words = set(chunk_lower.split())
        
        # Simple overlap score
        overlap = len(query_words & chunk_words)
        scored.append((overlap, i, chunk))
    
    # Sort by score (descending)
    scored.sort(reverse=True)
    
    # Return top-k
    return [chunk for _, _, chunk in scored[:top_k]]


class DomainBrief:
    """
    Maintains a small summary of a domain for context compression.
    """
    
    def __init__(self, domain: str):
        self.domain = domain
        self.summary: Optional[str] = None
        self.key_concepts: List[str] = []
        self.last_updated: Optional[datetime] = None
    
    def update(self, summary: str, key_concepts: List[str]) -> None:
        """Update domain brief."""
        self.summary = summary
        self.key_concepts = key_concepts
        self.last_updated = datetime.utcnow()
        logger.debug(f"Updated domain brief for '{self.domain}'")
    
    def get_context(self, max_length: int = 500) -> str:
        """
        Get compressed context for LLM.
        
        Args:
            max_length: Maximum length of context (characters)
        
        Returns:
            Compressed context string
        """
        parts = []
        
        if self.summary:
            parts.append(f"Domain: {self.domain}\nSummary: {self.summary[:max_length//2]}")
        
        if self.key_concepts:
            concepts_str = ", ".join(self.key_concepts[:10])  # Limit to 10 concepts
            parts.append(f"Key concepts: {concepts_str}")
        
        context = "\n".join(parts)
        if len(context) > max_length:
            context = context[:max_length] + "..."
        
        return context


# Global domain briefs cache
_domain_briefs: Dict[str, DomainBrief] = {}


def get_domain_brief(domain: str) -> DomainBrief:
    """Get or create domain brief."""
    if domain not in _domain_briefs:
        _domain_briefs[domain] = DomainBrief(domain)
    return _domain_briefs[domain]


def compress_kg_context(
    node_ids: List[str],
    max_nodes: int = 10,
) -> Dict[str, Any]:
    """
    Compress KG context by retrieving only neighborhood subgraph.
    
    Args:
        node_ids: List of node IDs to include
        max_nodes: Maximum number of nodes to include
    
    Returns:
        Compressed KG context (nodes and edges)
    """
    # For now, just limit to first max_nodes
    # Can be enhanced to retrieve actual subgraph from Neo4j
    return {
        "node_ids": node_ids[:max_nodes],
        "note": f"Retrieved {min(len(node_ids), max_nodes)} of {len(node_ids)} nodes",
    }
