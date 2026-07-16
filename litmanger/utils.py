"""Shared utilities — DOI parsing, safe paths, HTTP helpers."""

from __future__ import annotations

import logging
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("litmanger")

# ── HTTP ──────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def make_ssl_context() -> ssl.SSLContext:
    """Return a default SSL context for HTTP requests."""
    return ssl.create_default_context()


def fetch_page(
    url: str, timeout: int = 15, *, use_ssl_context: bool = False
) -> tuple[str, str]:
    """Fetch a URL, returning (html, final_url)."""
    headers = BROWSER_HEADERS
    req = urllib.request.Request(url, headers=headers)
    ctx = make_ssl_context() if use_ssl_context else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def normalize_author_name(name: str) -> str:
    """Convert 'LastName, FirstName' to 'FirstName LastName'."""
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
    return name


# ── DOI ───────────────────────────────────────────────────

DOI_RE = re.compile(r"/(10\.\d{4,}/[^/?&#]+)")
DOI_BARE_RE = re.compile(r"(10\.\d{4,}/[^?&#\"\'\s<>]+)")
DOI_IN_HTML_RE = re.compile(r"doi\.org/(10\.\d{4,}/[^\s\"\'<>]+)", re.I)

_STRIP_SUFFIXES = (".abstract", ".full", ".pdf", ".meta")


def extract_doi(url: str) -> str | None:
    """Extract a DOI from a URL or text.

    Handles DOI.org URLs, journal URLs, and bare DOI strings.
    Strips known non-DOI suffixes (.abstract, .full, .pdf, .meta).
    """
    # Try URL-path pattern first (most precise)
    m = DOI_RE.search(url)
    if m:
        return m.group(1)
    # Try broad bare DOI pattern (handles paste text)
    m = DOI_BARE_RE.search(url)
    if m:
        doi = m.group(1).rstrip(".")
        for suffix in _STRIP_SUFFIXES:
            if doi.endswith(suffix):
                doi = doi[: -len(suffix)]
        return doi
    return None


def extract_doi_from_html(html: str) -> str | None:
    """Extract DOI from HTML page content (meta tags, links)."""
    m = re.search(r'<meta\s+name="citation_doi"\s+content="([^"]+)"', html, re.I)
    if m:
        return m.group(1).rstrip(".")
    m = re.search(r"<meta\s+name='citation_doi'\s+content='([^']+)'", html, re.I)
    if m:
        return m.group(1).rstrip(".")
    m = DOI_IN_HTML_RE.search(html)
    if m:
        return m.group(1).rstrip(".")
    return None


def paper_id_from_doi(doi: str) -> str:
    """Convert a DOI into a short paper ID (last segment)."""
    return doi.split("/")[-1]


# ── Path safety ───────────────────────────────────────────

def safe_path_under(base: Path, requested: str) -> Path | None:
    """Resolve `requested` relative to `base`, returning None if it escapes.

    Handles absolute paths and `..` traversal attempts safely.
    """
    base_resolved = base.resolve()
    # Strip leading slash(es) to force relative treatment,
    # but check for traversal characters first
    cleaned = requested.lstrip("/").lstrip("\\")
    if ".." in cleaned.split("/") or ".." in cleaned.split("\\"):
        # Suspicious — resolve and check containment
        candidate = (base_resolved / cleaned).resolve()
        try:
            candidate.relative_to(base_resolved)
            return candidate
        except ValueError:
            return None
    resolved = (base_resolved / cleaned).resolve()
    try:
        resolved.relative_to(base_resolved)
        return resolved
    except ValueError:
        return None


# ── HTML helpers ──────────────────────────────────────────

def extract_meta_name(html: str, name: str) -> str | None:
    """Extract <meta name="X" content="Y"> — handles single and double quotes."""
    # Try double-quoted
    m = re.search(rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"', html, re.I)
    if m:
        return m.group(1)
    # Try single-quoted
    m = re.search(rf"<meta\s+name='{re.escape(name)}'\s+content='([^']*)'", html, re.I)
    if m:
        return m.group(1)
    return None


def extract_meta_property(html: str, prop: str) -> str | None:
    """Extract <meta property="og:..." content="...">."""
    m = re.search(rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"', html, re.I)
    if m:
        return m.group(1)
    return None


def extract_meta_names(html: str, name: str) -> list[str]:
    """Extract all <meta name="X" content="Y"> values (e.g., citation_author)."""
    results = []
    for m in re.finditer(
        rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"', html, re.I
    ):
        results.append(m.group(1))
    return results
