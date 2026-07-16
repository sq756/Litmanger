"""PDF downloader — browser cookie support for institutional access."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path

from .models import Paper
from .utils import USER_AGENT

logger = logging.getLogger("litmanger.pdf")


def _load_browser_cookies(domain_contains: str = "aps.org"):
    """Try to extract cookies from installed browsers via browser_cookie3."""
    try:
        import browser_cookie3

        loaders = [
            ("Chrome", lambda: browser_cookie3.chrome(domain_name=domain_contains)),
            ("Edge", lambda: browser_cookie3.edge(domain_name=domain_contains)),
            ("Brave", lambda: browser_cookie3.brave(domain_name=domain_contains)),
            ("Firefox", lambda: browser_cookie3.firefox(domain_name=domain_contains)),
            ("Chromium", lambda: browser_cookie3.chromium(domain_name=domain_contains)),
        ]
        for browser_name, loader in loaders:
            try:
                cj = loader()
                cookies_list = list(cj)
                if cookies_list:
                    return cookies_list, browser_name
            except Exception:
                continue
    except ImportError:
        logger.debug("browser_cookie3 not installed")
    return None, None


def _download_with_requests(
    urls: list[str],
    cookies: list,
    save_path: Path,
    timeout: int = 30,
) -> str | None:
    """Download a PDF using requests + browser cookies."""
    try:
        import requests
    except ImportError:
        logger.warning("'requests' library not installed — install for better PDF download")
        return None

    cookie_dict = {}
    for c in cookies:
        cookie_dict[c.name] = c.value

    for url in urls:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                cookies=cookie_dict,
                allow_redirects=True,
                timeout=timeout,
            )
            if r.status_code == 200 and len(r.content) > 1000:
                is_pdf = b"%PDF" in r.content[:1024]
                ct = r.headers.get("Content-Type", "")
                if is_pdf or "pdf" in ct.lower() or "octet-stream" in ct.lower():
                    save_path.write_bytes(r.content)
                    return save_path.name
        except Exception:
            continue
    return None


def _download_with_urllib(urls: list[str], save_path: Path, timeout: int = 20) -> str | None:
    """Fallback: download PDF with plain urllib (no cookies)."""
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if len(data) > 5000 and b"%PDF" in data[:1024]:
                    save_path.write_bytes(data)
                    return save_path.name
        except Exception:
            continue
    return None


def download_pdf(
    paper: Paper,
    pdf_dir: Path,
    timeout: int = 30,
) -> str | None:
    """Download a paper's PDF to `pdf_dir/<paper.id>.pdf`.

    Tries in order:
    1. Browser cookies (institutional access via browser_cookie3 + requests)
    2. Direct download via urllib (for open-access papers)

    Returns the filename on success, None on failure.
    """
    doi = paper.doi
    paper_id = paper.id
    pdf_url = paper.pdf_url or f"https://journals.aps.org/prb/pdf/{doi}"

    save_path = pdf_dir / f"{paper_id}.pdf"

    # Build candidate URLs
    urls = [pdf_url]
    if "aps.org" in doi.lower() or "PhysRev" in doi:
        urls.append(f"https://link.aps.org/pdf/{doi}")
    if "arxiv" in pdf_url.lower():
        urls.append(f"https://arxiv.org/pdf/{paper_id}.pdf")

    # Remove duplicates while preserving order
    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    logger.info("Downloading PDF for %s…", paper_id)

    # ── Strategy 1: browser cookies ──
    cookies, browser_name = _load_browser_cookies()
    if cookies:
        logger.info("Found %d cookies from %s", len(cookies), browser_name)
        result = _download_with_requests(urls, cookies, save_path, timeout=timeout)
        if result:
            size_kb = save_path.stat().st_size / 1024
            logger.info("PDF saved: %s (%.0f KB)", result, size_kb)
            return result

    # ── Strategy 2: direct urllib ──
    result = _download_with_urllib(urls, save_path, timeout=timeout)
    if result:
        size_kb = save_path.stat().st_size / 1024
        logger.info("PDF saved (direct): %s (%.0f KB)", result, size_kb)
        return result

    logger.warning("Auto-download failed — institutional access may be required")
    return None
