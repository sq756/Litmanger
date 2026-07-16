"""Paper metadata fetcher — extensible publisher support.

Each publisher module is a function that takes (html, final_url, doi) and
returns a dict of Paper fields to update.  Register them with @register().
"""

from __future__ import annotations

import logging
import re
import urllib.request
from typing import Callable

from .models import Paper
from .utils import (
    USER_AGENT,
    DOI_RE,
    extract_doi,
    extract_meta_name,
    extract_meta_names,
    extract_meta_property,
    fetch_page,
    paper_id_from_doi,
)

logger = logging.getLogger("litmanger.fetcher")

# ── Type ──────────────────────────────────────────────────
# A publisher fetcher receives (html, final_url, doi) and returns a dict
# of extra fields for a Paper constructor.
PublisherFetcher = Callable[[str, str, str], dict]


# ── Registry ──────────────────────────────────────────────

_fetchers: list[tuple[str, PublisherFetcher]] = []


def register(name: str):
    """Decorator to register a publisher-specific fetcher."""

    def deco(fn: PublisherFetcher) -> PublisherFetcher:
        _fetchers.append((name, fn))
        return fn

    return deco


# ══════════════════════════════════════════════════════════
#  Publisher-specific fetchers
# ══════════════════════════════════════════════════════════


@register("aps")
def _fetch_aps(html: str, final_url: str, doi: str) -> dict:
    """APS journal pages: Physical Review A/B/C/D/E/X/Letters, RMP, etc."""
    info: dict = {}

    # Standard citation_* meta tags (APS is good about these)
    info["title"] = extract_meta_name(html, "citation_title") or ""
    info["authors"] = extract_meta_names(html, "citation_author")
    info["journal"] = extract_meta_name(html, "citation_journal_title") or ""
    info["abstract"] = extract_meta_name(html, "citation_abstract") or ""

    pub_date = extract_meta_name(html, "citation_date") or ""
    if pub_date:
        parts = pub_date.split("/")
        info["year"] = parts[0] if len(parts) > 0 else ""
        info["month"] = parts[1] if len(parts) > 1 else ""

    pdf_url = extract_meta_name(html, "citation_pdf_url")
    if pdf_url:
        info["pdf_url"] = pdf_url
    else:
        info["pdf_url"] = f"https://journals.aps.org/prb/pdf/{doi}"

    info["publisher"] = "American Physical Society"

    return info


@register("arxiv")
def _fetch_arxiv(html: str, final_url: str, doi: str) -> dict:
    """arXiv abstract pages."""
    info: dict = {}

    # Title from og:title or citation_title
    og_title = extract_meta_property(html, "og:title")
    if og_title:
        # Strip "[date] " prefix that arXiv uses
        m = re.match(r"^\[\d{4}\.\d{5}\]\s*(.*)", og_title)
        info["title"] = m.group(1) if m else og_title
    else:
        info["title"] = extract_meta_name(html, "citation_title") or ""

    info["authors"] = extract_meta_names(html, "citation_author")

    # Build PDF URL from abstract URL
    arxiv_id = ""
    m = re.search(r"arxiv\.org/abs/([\d.]+(?:v\d+)?)", final_url)
    if m:
        arxiv_id = m.group(1)
    else:
        # Try to get from DOI
        arxiv_id = doi.split("/")[-1]
    info["pdf_url"] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    info["journal"] = "arXiv"
    info["publisher"] = "arXiv"

    pub_date = extract_meta_name(html, "citation_date") or ""
    info["year"] = pub_date[:4] if pub_date else ""

    abstract = extract_meta_name(html, "citation_abstract")
    if abstract:
        info["abstract"] = abstract

    return info


@register("nature")
def _fetch_nature(html: str, final_url: str, doi: str) -> dict:
    """Nature.com articles."""
    info: dict = {}

    info["title"] = (
        extract_meta_name(html, "citation_title")
        or extract_meta_name(html, "dc.Title")
        or extract_meta_property(html, "og:title")
        or ""
    )
    info["authors"] = extract_meta_names(html, "citation_author")
    info["journal"] = extract_meta_name(html, "citation_journal_title") or ""

    pub_date = extract_meta_name(html, "citation_date") or extract_meta_name(html, "dc.Date") or ""
    info["year"] = pub_date[:4] if pub_date else ""

    pdf_url = extract_meta_name(html, "citation_pdf_url")
    info["pdf_url"] = pdf_url or f"https://www.nature.com/articles/{doi.split('/')[-1]}.pdf"

    info["publisher"] = "Nature Publishing Group"

    abstract = extract_meta_name(html, "citation_abstract") or extract_meta_name(html, "dc.Description")
    if abstract:
        info["abstract"] = abstract

    return info


@register("generic")
def _fetch_generic(html: str, final_url: str, doi: str) -> dict:
    """Generic fallback — try common meta patterns."""
    info: dict = {}

    # Try citation_* meta first
    info["title"] = (
        extract_meta_name(html, "citation_title")
        or extract_meta_property(html, "og:title")
        or extract_meta_name(html, "dc.Title")
        or _extract_title_tag(html)
        or ""
    )
    info["authors"] = extract_meta_names(html, "citation_author")
    info["journal"] = extract_meta_name(html, "citation_journal_title") or ""

    pub_date = extract_meta_name(html, "citation_date") or ""
    info["year"] = pub_date[:4] if pub_date else ""

    pdf_url = extract_meta_name(html, "citation_pdf_url")
    if not pdf_url:
        # Guess from common patterns
        pdf_url = _guess_pdf_url(final_url, doi)
    info["pdf_url"] = pdf_url or ""

    abstract = extract_meta_name(html, "citation_abstract") or extract_meta_name(html, "dc.Description")
    if abstract:
        info["abstract"] = abstract

    return info


def _extract_title_tag(html: str) -> str | None:
    """Extract <title>...</title> as last resort."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else None


def _guess_pdf_url(url: str, doi: str) -> str | None:
    """Try to guess a PDF URL from known patterns."""
    if "arxiv.org" in url:
        m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
        if m:
            return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    return None


# ══════════════════════════════════════════════════════════
#  BibTeX
# ══════════════════════════════════════════════════════════


def fetch_aps_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from APS export endpoint."""
    bib_url = f"https://journals.aps.org/prb/export/{doi}?type=bibtex"
    try:
        req = urllib.request.Request(bib_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.debug("APS BibTeX fetch failed for %s", doi)
        return None


def fetch_crossref_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from Crossref API (content negotiation)."""
    url = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.debug("Crossref BibTeX fetch failed for %s", doi)
        return None


def fetch_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX, trying Crossref first, then publisher-specific endpoints."""
    bib = fetch_crossref_bibtex(doi, timeout)
    if bib:
        return bib
    bib = fetch_aps_bibtex(doi, timeout)
    if bib:
        return bib
    return None


# ══════════════════════════════════════════════════════════
#  Main fetcher
# ══════════════════════════════════════════════════════════


def _detect_publisher(url: str) -> str:
    """Guess which publisher fetcher to use from the URL."""
    url_lower = url.lower()
    if "aps.org" in url_lower or "link.aps" in url_lower:
        return "aps"
    if "arxiv.org" in url_lower:
        return "arxiv"
    if "nature.com" in url_lower:
        return "nature"
    return "generic"


def _enrich_from_bibtex(paper: Paper, bibtex: str) -> None:
    """Extract volume/issue/pages from a BibTeX entry."""
    for field, attr in [("volume", "volume"), ("number", "issue"), ("pages", "pages")]:
        m = re.search(rf'{field}\s*=\s*\{{([^}}]+)\}}', bibtex)
        if m and not getattr(paper, attr):
            setattr(paper, attr, m.group(1))

    # Try to extract month
    m = re.search(r'month\s*=\s*\{{([^}}]+)\}}', bibtex)
    if m and not paper.month:
        paper.month = m.group(1)


def collect_paper(url: str, timeout: int = 15) -> Paper | None:
    """Given a journal URL, fetch HTML, extract metadata, return a Paper object.

    Returns None if the DOI couldn't be extracted or the page couldn't be fetched.
    """
    doi = extract_doi(url)
    if not doi:
        logger.error("Could not extract DOI from: %s", url)
        return None

    logger.info("DOI: %s", doi)
    logger.info("Fetching page…")

    try:
        html, final_url = fetch_page(url, timeout=timeout)
    except Exception as exc:
        logger.error("Failed to fetch page: %s", exc)
        return None

    # Use the appropriate publisher fetcher
    publisher = _detect_publisher(final_url)
    logger.info("Detected publisher: %s", publisher)

    fetcher = dict(_fetchers).get(publisher, _fetch_generic)
    info = fetcher(html, final_url, doi)

    # Build the paper object
    paper_id = paper_id_from_doi(doi)
    paper = Paper(
        id=paper_id,
        doi=doi,
        url=url,
        **{k: v for k, v in info.items() if v},
    )

    # Fetch BibTeX
    logger.info("Fetching BibTeX…")
    bibtex = fetch_bibtex(doi, timeout=timeout)
    if bibtex:
        paper.bibtex = bibtex
        _enrich_from_bibtex(paper, bibtex)
        logger.info("BibTeX retrieved")
    else:
        logger.warning("No BibTeX available")

    # Summary
    logger.info("  Title: %s", paper.title)
    logger.info("  Authors: %s", paper.author_line)
    logger.info("  Journal: %s", paper.journal)
    if paper.year:
        logger.info("  Year: %s", paper.year)

    return paper
