"""Shared utilities — DOI parsing, safe paths, HTTP helpers."""

from __future__ import annotations

import logging
import re
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger("litmanger")

# ── HTTP ──────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch_page(url: str, timeout: int = 15) -> tuple[str, str]:
    """Fetch a URL, returning (html, final_url)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


# ── DOI ───────────────────────────────────────────────────

DOI_RE = re.compile(r"/(10\.\d{4,}/[^/?&#]+)")


def extract_doi(url: str) -> str | None:
    """Extract a DOI from a URL or text.

    Examples:
        https://journals.aps.org/prb/abstract/10.1103/PhysRevB.113.235157
          → 10.1103/PhysRevB.113.235157
        https://doi.org/10.1038/s41586-023-12345
          → 10.1038/s41586-023-12345
        10.1002/adma.202301234 → 10.1002/adma.202301234
    """
    # Try the URL path pattern first
    m = DOI_RE.search(url)
    if m:
        return m.group(1)
    # Try bare DOI pattern anywhere in the text
    m = re.search(r"(10\.\d{4,}/[^\s]+)", url)
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
