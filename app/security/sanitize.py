"""
Content sanitization: strip scripts, ignore hidden text tricks.
Applied to any retrieved/crawled content before use or storage.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Zero-width and invisible characters (used for hidden text / steganography)
INVISIBLE_CHARS = re.compile(
    r"[\u200b-\u200d\u2060\u2061\u2062\u2063\ufeff\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e\u2000-\u200f\u2028-\u202f\u205f-\u2064\u206a-\u206f\ufeff]"
)

# Script/style tag content (strip entirely)
SCRIPT_STYLE_PATTERN = re.compile(
    r"<(?:script|style|iframe|object|embed|form)[^>]*>.*?</(?:script|style|iframe|object|embed|form)>",
    re.DOTALL | re.IGNORECASE
)

# HTML comments (can hide malicious content)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)

# data: and javascript: URLs
DATA_JS_URI_PATTERN = re.compile(
    r"(?:data|javascript|vbscript):[^\s\)\]\"]*",
    re.IGNORECASE
)

# on* event handlers
ON_EVENT_PATTERN = re.compile(
    r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']",
    re.IGNORECASE
)

# CSS that hides text (display:none, visibility:hidden, etc.)
HIDDEN_CSS_PATTERN = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|height\s*:\s*0|width\s*:\s*0|opacity\s*:\s*0|position\s*:\s*absolute\s*;\s*left\s*:\s*-9999",
    re.IGNORECASE
)


def strip_invisible(text: str) -> str:
    """Remove zero-width and invisible Unicode characters."""
    if not text:
        return ""
    return INVISIBLE_CHARS.sub("", text)


def strip_scripts_and_style(html: str) -> str:
    """Remove script, style, iframe, object, embed, form tags and their content."""
    if not html:
        return ""
    return SCRIPT_STYLE_PATTERN.sub(" ", html)


def strip_html_comments(html: str) -> str:
    """Remove HTML comments."""
    if not html:
        return ""
    return HTML_COMMENT_PATTERN.sub(" ", html)


def strip_dangerous_uris(text: str) -> str:
    """Remove data:, javascript:, vbscript: URIs."""
    if not text:
        return ""
    return DATA_JS_URI_PATTERN.sub(" [removed]", text)


def strip_event_handlers(html: str) -> str:
    """Remove on* event handler attributes."""
    if not html:
        return ""
    return ON_EVENT_PATTERN.sub("", html)


def strip_hidden_css_blocks(html: str) -> str:
    """
    Remove blocks that use CSS to hide content (display:none, etc.).
    Simple heuristic: remove style attributes that contain hidden patterns.
    """
    if not html:
        return ""
    # Remove style="...display:none..."
    def _replace_style(match: re.Match) -> str:
        style = match.group(1)
        if HIDDEN_CSS_PATTERN.search(style):
            return ""
        return match.group(0)
    return re.sub(r'style\s*=\s*["\']([^"\']*)["\']', _replace_style, html, flags=re.IGNORECASE)


def sanitize_content(
    content: Optional[str],
    content_type: str = "html",
    max_length: int = 500_000,
) -> str:
    """
    Sanitize retrieved content: strip scripts, hidden text, dangerous URIs.
    
    Args:
        content: Raw content (HTML or plain text)
        content_type: "html" or "text"
        max_length: Maximum length to return
    
    Returns:
        Sanitized string safe for downstream use
    """
    if not content or not isinstance(content, str):
        return ""
    
    if len(content) > max_length:
        content = content[:max_length] + "..."
        logger.debug(f"Content truncated to {max_length} chars")
    
    # Always strip invisible chars
    out = strip_invisible(content)
    
    if content_type.lower() == "html":
        out = strip_scripts_and_style(out)
        out = strip_html_comments(out)
        out = strip_event_handlers(out)
        out = strip_hidden_css_blocks(out)
    
    out = strip_dangerous_uris(out)
    
    # Normalize whitespace
    out = re.sub(r"\s+", " ", out).strip()
    
    return out


def sanitize_for_llm(text: Optional[str], max_length: int = 50_000) -> str:
    """
    Sanitize text before sending to LLM (prevents injection via content).
    Strips invisible chars and truncates; use with wrap_untrusted_content.
    """
    if not text or not isinstance(text, str):
        return ""
    out = strip_invisible(text)
    out = strip_dangerous_uris(out)
    if len(out) > max_length:
        out = out[:max_length] + "..."
    return out.strip()
