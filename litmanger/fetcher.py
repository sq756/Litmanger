"""Paper metadata fetcher — extensible publisher support.

Each publisher module is a function that takes (html, final_url, doi) and
returns a dict of Paper fields to update.  Register them with @register().
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Callable

from .models import Paper
from .utils import (
    BROWSER_HEADERS,
    USER_AGENT,
    extract_doi,
    extract_doi_from_html,
    extract_meta_name,
    extract_meta_names,
    extract_meta_property,
    fetch_page,
    make_ssl_context,
    normalize_author_name,
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
        pdf_url = _guess_pdf_url(final_url, doi, html)
    info["pdf_url"] = pdf_url or ""

    abstract = extract_meta_name(html, "citation_abstract") or extract_meta_name(html, "dc.Description")
    if abstract:
        info["abstract"] = abstract

    return info


def _extract_title_tag(html: str) -> str | None:
    """Extract <title>...</title> as last resort."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else None


def _guess_pdf_url(url: str = "", doi: str = "", html: str = "") -> str | None:  # noqa: C901
    """Try to guess a PDF URL from known publisher patterns and meta tags."""
    url_lower = url.lower()
    doi_suffix = doi.split("/")[-1] if doi else ""

    # First try meta tag
    if html:
        pdf_meta = extract_meta_name(html, "citation_pdf_url")
        if pdf_meta:
            return pdf_meta

    # arXiv
    if "arxiv.org" in url_lower:
        m = re.search(r"arxiv\.org/abs/([\d.]+(?:v\d+)?)", url)
        if m:
            return f"https://arxiv.org/pdf/{m.group(1)}.pdf"

    # Publisher-specific patterns
    patterns = [
        ("nature.com", f"https://www.nature.com/articles/{doi_suffix}.pdf"),
        ("aps.org", f"https://journals.aps.org/prb/pdf/{doi}"),
        ("science.org", f"https://www.science.org/doi/pdf/{doi}"),
        ("sciencemag.org", f"https://www.science.org/doi/pdf/{doi}"),
        ("ieee.org", f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={doi_suffix}"),
        ("acm.org", f"https://dl.acm.org/doi/pdf/{doi}"),
        ("springer.com", f"https://link.springer.com/content/pdf/{doi}.pdf"),
        ("sciencedirect.com", f"https://www.sciencedirect.com/science/article/pii/{doi_suffix}/pdf"),
        ("elsevier", f"https://www.sciencedirect.com/science/article/pii/{doi_suffix}/pdf"),
        ("wiley.com", f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"),
        ("acs.org", f"https://pubs.acs.org/doi/pdf/{doi}"),
        ("iop.org", f"https://iopscience.iop.org/article/{doi}/pdf"),
        ("tandfonline.com", f"https://www.tandfonline.com/doi/pdf/{doi}"),
        ("oup.com", f"https://academic.oup.com/redirect/{doi}/pdf"),
        ("pnas.org", f"https://www.pnas.org/doi/pdf/{doi}"),
    ]
    for domain, pdf_url in patterns:
        if domain in url_lower:
            return pdf_url

    # URL path rewriting patterns
    if "/abstract/" in url:
        return url.replace("/abstract/", "/pdf/")
    if "/abs/" in url:
        return url.replace("/abs/", "/pdf/")

    # Fallback
    if doi:
        return f"https://doi.org/{doi}"
    return None


# ══════════════════════════════════════════════════════════
#  Crossref metadata fallback
# ══════════════════════════════════════════════════════════


def fetch_crossref_metadata(doi: str, timeout: int = 15) -> dict | None:  # noqa: C901
    """Fetch paper metadata from Crossref API as fallback when HTML is unavailable."""
    try:
        api_url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
        req = urllib.request.Request(api_url, headers=BROWSER_HEADERS)
        ctx = make_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.debug("Crossref metadata fetch failed for %s", doi)
        return None

    msg = result.get("message")
    if not msg:
        return None

    info: dict = {}

    if title_list := msg.get("title"):
        info["title"] = title_list[0]

    authors = []
    for a in msg.get("author", []):
        family = a.get("family", "")
        given = a.get("given", "")
        name = f"{given} {family}".strip() if given else family
        if name:
            authors.append(normalize_author_name(name) if "," in name else name)
    if authors:
        info["authors"] = authors

    if container := msg.get("container-title"):
        info["journal"] = container[0] if isinstance(container, list) else container

    pub_date = msg.get("published-print", {}).get("date-parts") or msg.get("created", {}).get("date-parts")
    if pub_date and pub_date[0]:
        info["year"] = str(pub_date[0][0])
        if len(pub_date[0]) > 1:
            info["month"] = str(pub_date[0][1])

    if abstract := msg.get("abstract"):
        abstract = re.sub(r"<[^>]+>", "", abstract)
        info["abstract"] = abstract[:2000]

    for key in ("volume", "issue", "pages", "publisher"):
        if v := msg.get(key):
            info[key] = str(v)

    for link in msg.get("link", []):
        if link.get("content-type") in ("application/pdf", "text/xml"):
            info["pdf_url"] = link.get("URL", "")
            break

    return info if info else None


# ══════════════════════════════════════════════════════════
#  BibTeX
# ══════════════════════════════════════════════════════════


def fetch_aps_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from APS export endpoint."""
    bib_url = f"https://journals.aps.org/prb/export/{doi}?type=bibtex"
    try:
        req = urllib.request.Request(bib_url, headers=BROWSER_HEADERS)
        ctx = make_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.debug("APS BibTeX fetch failed for %s", doi)
        return None


def fetch_crossref_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from Crossref API (content negotiation)."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}/transform/application/x-bibtex"
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        ctx = make_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            if data.strip().startswith("@"):
                return data
    except Exception:
        logger.debug("Crossref BibTeX fetch failed for %s", doi)
        return None
    return None


def fetch_doi_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from dx.doi.org content negotiation."""
    try:
        req = urllib.request.Request(
            f"https://dx.doi.org/{doi}",
            headers={**BROWSER_HEADERS, "Accept": "text/bibliography; style=bibtex"},
        )
        ctx = make_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            if data.strip().startswith("<"):
                return None
            return data
    except Exception:
        logger.debug("dx.doi.org BibTeX fetch failed for %s", doi)
        return None


def fetch_bibtex(doi: str, timeout: int = 15) -> str | None:
    """Fetch BibTeX from multiple sources: Crossref → APS → dx.doi.org."""
    bib = fetch_crossref_bibtex(doi, timeout)
    if bib:
        return bib
    bib = fetch_aps_bibtex(doi, timeout)
    if bib:
        return bib
    return fetch_doi_bibtex(doi, timeout)


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

    Handles: DOI URLs, arXiv IDs, crossref fallback, and multi-publisher meta tags.
    Returns None if the DOI couldn't be extracted or all fetch methods failed.
    """
    # Normalize bare DOI to URL
    if url.startswith("10.") and not url.startswith("http"):
        url = "https://doi.org/" + url

    # Try to extract DOI from URL first
    doi = extract_doi(url)
    arxiv_id = None
    if "arxiv.org" in url:
        m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
        arxiv_id = m.group(1) if m else None

    logger.info("DOI: %s (arxiv: %s)", doi, arxiv_id)
    logger.info("Fetching page…")

    # Fetch the HTML page (with graceful fallback)
    html = None
    final_url = url
    crossref_meta = None
    try:
        html, final_url = fetch_page(url, timeout=timeout, use_ssl_context=True)
    except Exception:
        logger.warning("Page fetch failed, trying Crossref API")

    # If page fetch failed, get metadata from Crossref
    if not html and doi:
        crossref_meta = fetch_crossref_metadata(doi, timeout=timeout)

    # If we have HTML but no DOI yet, extract from HTML
    if html and not doi and not arxiv_id:
        doi = extract_doi_from_html(html) or extract_doi(final_url)

    # arXiv: extract DOI from HTML links
    if arxiv_id and not doi and html:
        m = re.search(r'<a\s+[^>]*href="https?://doi\.org/(10\.\d{4,}/[^"]+)"[^>]*>', html, re.I)
        if m:
            doi = m.group(1).rstrip(".")

    if not doi and not arxiv_id:
        logger.error("Could not extract DOI or arXiv ID from: %s", url)
        return None

    # If crossref fallback gave us everything (HTML fetch failed)
    if crossref_meta and not html:
        paper_id = paper_id_from_doi(doi) if doi else (arxiv_id or "unknown")
        paper = Paper(
            id=paper_id,
            doi=doi or "",
            url=url,
            **{k: v for k, v in crossref_meta.items() if v},
        )
        logger.info("  Title: %s", paper.title)
        logger.info("  Authors: %s", paper.author_line)
        return paper

    # Use the appropriate publisher fetcher
    publisher = _detect_publisher(final_url)
    logger.info("Detected publisher: %s", publisher)

    fetcher = dict(_fetchers).get(publisher, _fetch_generic)
    info = fetcher(html, final_url, doi)

    # Decode HTML entities in title
    if title := info.get("title"):
        info["title"] = (
            title.replace("&#39;", "'")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

    # Build the paper object
    paper_id = paper_id_from_doi(doi) if doi else (arxiv_id or "unknown")
    paper = Paper(
        id=paper_id,
        doi=doi or "",
        url=url,
        **{k: v for k, v in info.items() if v},
    )

    if arxiv_id:
        paper.arxiv_id = arxiv_id

    # Fetch BibTeX
    if doi:
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
