"""
Network egress controls: allowlist domains for crawling/fetching.
Only URLs whose host is in the allowlist can be fetched.
"""
import logging
import re
from urllib.parse import urlparse
from typing import Set, Optional
import os

logger = logging.getLogger(__name__)

# Default allowlist: known-safe academic and educational domains
DEFAULT_ALLOWED_DOMAINS: Set[str] = {
    "api.semanticscholar.org",
    "semanticscholar.org",
    "export.arxiv.org",
    "arxiv.org",
    "api.openalex.org",
    "openalex.org",
    "en.wikipedia.org",
    "www.wikipedia.org",
    "wikipedia.org",
    "api.rest.v1.page.wikipedia.org",
    "openstax.org",
    "www.openstax.org",
    "khanacademy.org",
    "www.khanacademy.org",
    "ocw.mit.edu",
    "www.ocw.mit.edu",
    "libretexts.org",
    "doi.org",
    "crossref.org",
    "api.crossref.org",
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "api.reddit.com",
    "twitter.com",
    "x.com",
}

# Regex for valid host (subdomain.domain.tld)
_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$")


def _normalize_domain(domain: str) -> str:
    """Normalize domain to lowercase, strip whitespace."""
    if not domain:
        return ""
    return domain.lower().strip()


def _extract_host(url: str) -> Optional[str]:
    """Extract host from URL. Returns None if URL is invalid."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return None
        host = parsed.netloc.split(":")[0]  # strip port
        if _HOST_PATTERN.match(host):
            return _normalize_domain(host)
        return None
    except Exception:
        return None


class NetworkAllowlist:
    """Allowlist of domains that can be fetched."""
    _domains: Set[str] = set(DEFAULT_ALLOWED_DOMAINS)

    @classmethod
    def add(cls, domain: str) -> None:
        cls._domains.add(_normalize_domain(domain))

    @classmethod
    def remove(cls, domain: str) -> None:
        cls._domains.discard(_normalize_domain(domain))

    @classmethod
    def contains(cls, domain: str) -> bool:
        """Check if exact domain is allowed."""
        return _normalize_domain(domain) in cls._domains

    @classmethod
    def is_url_allowed(cls, url: str) -> bool:
        """
        Check if URL is allowed for fetch.
        Returns True if host is in allowlist.
        """
        host = _extract_host(url)
        if not host:
            return False
        # Exact match
        if host in cls._domains:
            return True
        # Subdomain match: e.g. api.example.com when example.com is allowed
        for allowed in cls._domains:
            if host == allowed or host.endswith("." + allowed):
                return True
        return False

    @classmethod
    def list_domains(cls) -> Set[str]:
        return set(cls._domains)


def is_url_allowed(url: str) -> bool:
    """Check if URL is allowed for network egress (crawling/fetching)."""
    allowed = NetworkAllowlist.is_url_allowed(url)
    if not allowed:
        logger.warning(f"URL not in allowlist, blocked: {url[:80]}...")
    return allowed


def get_allowed_domains() -> Set[str]:
    """Return current allowlist of domains."""
    return NetworkAllowlist.list_domains()


# Load additional domains from env (comma-separated)
_env_domains = os.getenv("SECURITY_NETWORK_ALLOWLIST", "")
if _env_domains:
    for d in _env_domains.split(","):
        d = _normalize_domain(d)
        if d:
            NetworkAllowlist.add(d)
