"""
HTML parser fallback for when source HTML changes.
Enables graceful degradation when parser breaks.
"""
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HTMLParserError(Exception):
    """Raised when HTML parsing fails."""
    pass


def parse_html_simple(html: str) -> str:
    """
    Simple HTML parser: strip tags, extract text.
    Fallback when structured parsing fails.
    """
    if not html:
        return ""
    
    # Remove script/style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Decode entities (simple)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def parse_html_with_fallback(
    html: str,
    expected_fields: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Parse HTML with graceful fallback.
    
    Tries structured parsing first, falls back to simple text extraction.
    
    Args:
        html: Raw HTML
        expected_fields: Optional list of fields we expect (for validation)
    
    Returns:
        Dict with parsed content and metadata
    """
    result = {
        "content": "",
        "metadata": {
            "parser": "unknown",
            "fallback_used": False,
        },
    }
    
    # Try structured parsing (if we had BeautifulSoup, etc.)
    # For now, we always use simple fallback
    try:
        # Simple extraction
        text = parse_html_simple(html)
        result["content"] = text
        result["metadata"]["parser"] = "simple"
        result["metadata"]["fallback_used"] = True
        
        # Validate we got some content
        if len(text) < 10:
            raise HTMLParserError("Extracted text too short (< 10 chars)")
        
        logger.debug(f"HTML parsed: {len(text)} chars extracted")
        return result
        
    except Exception as e:
        logger.warning(f"HTML parsing failed: {e}, using minimal fallback")
        # Minimal fallback: just strip everything
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        result["content"] = text[:1000]  # Limit to 1000 chars
        result["metadata"]["parser"] = "minimal_fallback"
        result["metadata"]["fallback_used"] = True
        result["metadata"]["error"] = str(e)
        return result
