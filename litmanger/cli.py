"""Litmanger CLI — paper collection, dashboard, and management tools."""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser
from pathlib import Path

from .fetcher import collect_paper
from .models import PaperDB
from .pdf import download_pdf
from .server import run_server
from .templates import generate_html

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = SCRIPT_DIR / "papers.json"
PDF_DIR = SCRIPT_DIR / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("litmanger")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(levelname)-5s %(message)s"
    logging.basicConfig(level=level, format=fmt)
    # Keep external libs quiet
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def cmd_add(url: str, *, no_download: bool = False, verbose: bool = False) -> int:
    """Collect a paper from URL and optionally download its PDF."""
    _setup_logging(verbose)

    paper = collect_paper(url)
    if paper is None:
        print("[ERROR] Could not collect paper from URL")
        return 1

    db = PaperDB.load(DB_PATH)
    is_new = db.add(paper)
    db.save(DB_PATH)

    if is_new:
        print(f"[OK] Paper added: {paper.title[:80]}")
    else:
        print(f"[OK] Paper updated: {paper.title[:80]}")

    print(f"     Total: {db.count} papers, {db.pdf_count} PDFs")

    # PDF download
    if not no_download:
        print(f"\n{'—'*40}")
        print("PDF Download")
        print(f"{'—'*40}")
        local_path = download_pdf(paper, PDF_DIR)

        if local_path:
            db.mark_pdf(paper.id, str(PDF_DIR / local_path))
            db.save(DB_PATH)
            print(f"[OK] PDF saved: {local_path}")
            webbrowser.open(str((PDF_DIR / local_path).resolve()))
        else:
            print("[INFO] Auto-download failed (institutional access needed)")
            print(f"[INFO] Opening PDF in browser — use Ctrl+S to save to: {PDF_DIR}")
            webbrowser.open(paper.pdf_url or paper.url)

    # Update static HTML
    from .templates import save_html
    save_html(db, PDF_DIR, SCRIPT_DIR / "paper_library.html")

    print(f"\n{'='*60}")
    return 0


def cmd_list(_verbose: bool = False) -> int:
    """List all papers in the library."""
    _setup_logging(False)
    db = PaperDB.load(DB_PATH)

    _banner(f"Paper Library: {db.count} papers  |  PDFs: {PDF_DIR}")

    for i, p in enumerate(db.papers, 1):
        pdf_ok = "[OK]" if p.pdf_downloaded else "[  ]"
        print(f"\n{i:>3}. {pdf_ok} {p.title}")
        print(f"     {p.author_line}")
        if p.journal:
            parts = [p.journal]
            if p.year:
                parts.append(f"({p.year})")
            print(f"     {', '.join(parts)}")
        print(f"     DOI: {p.doi}")

    return 0


def cmd_download(paper_id: str, verbose: bool = False) -> int:
    """Download or re-download a paper's PDF."""
    _setup_logging(verbose)
    db = PaperDB.load(DB_PATH)

    paper = db.find_by_id(paper_id)
    if paper is None:
        print(f"[ERROR] Paper not found: {paper_id}")
        return 1

    print(f"Downloading: {paper.title[:80]}")
    local_path = download_pdf(paper, PDF_DIR)

    if local_path:
        db.mark_pdf(paper.id, str(PDF_DIR / local_path))
        db.save(DB_PATH)
        from .templates import save_html
        save_html(db, PDF_DIR, SCRIPT_DIR / "paper_library.html")
        print(f"[OK] Saved: {local_path}")
    else:
        print("[INFO] Opening PDF in browser for manual save…")
        webbrowser.open(paper.pdf_url or paper.url)
        print(f"[INFO] After downloading, move the file to: {PDF_DIR}")
        print(f"[INFO] Then run: python -m litmanger --mark-done {paper_id}")

    return 0


def cmd_open(paper_id: str, _verbose: bool = False) -> int:
    """Open a paper's PDF or URL in the browser."""
    db = PaperDB.load(DB_PATH)
    paper = db.find_by_id(paper_id)
    if paper is None:
        print(f"[ERROR] Paper not found: {paper_id}")
        return 1
    print(f"Opening: {paper.title[:80]}")
    webbrowser.open(paper.pdf_url or paper.url)
    return 0


def cmd_mark_done(paper_id: str, _verbose: bool = False) -> int:
    """Mark a paper's PDF as downloaded."""
    db = PaperDB.load(DB_PATH)
    if db.mark_pdf(paper_id):
        db.save(DB_PATH)
        from .templates import save_html
        save_html(db, PDF_DIR, SCRIPT_DIR / "paper_library.html")
        print(f"[OK] Marked {paper_id} as downloaded")
        return 0
    print(f"[ERROR] Paper not found: {paper_id}")
    return 1


def cmd_html(_verbose: bool = False) -> int:
    """Generate a static HTML dashboard."""
    db = PaperDB.load(DB_PATH)
    from .templates import save_html
    path = save_html(db, PDF_DIR, SCRIPT_DIR / "paper_library.html")
    print(f"[OK] Static HTML: {path}")
    return 0


def cmd_server(port: int = 8765, _verbose: bool = False) -> int:
    """Start the local dashboard server."""
    _setup_logging(False)
    from .server import PORT
    db = PaperDB.load(DB_PATH)
    run_server(db, PDF_DIR, SCRIPT_DIR, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for `litmanger` command and `python -m litmanger`."""

    parser = argparse.ArgumentParser(
        prog="litmanger",
        description="Academic paper manager — collect metadata and PDFs from journal URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  litmanger https://journals.aps.org/prb/abstract/10.1103/PhysRevB.113.235157
  litmanger --list
  litmanger server
  litmanger --download PhysRevB.113.235157
""",
    )

    parser.add_argument("url", nargs="?", help="Journal URL or DOI to add")
    parser.add_argument("--list", action="store_true", help="List all papers")
    parser.add_argument("--download", metavar="ID", help="Download PDF for a paper by ID")
    parser.add_argument("--open", metavar="ID", help="Open a paper's PDF/URL in the browser")
    parser.add_argument("--mark-done", metavar="ID", help="Mark a paper's PDF as downloaded")
    parser.add_argument("--html", action="store_true", help="Generate static HTML dashboard")
    parser.add_argument("--server", dest="serve", action="store_true", help="Start local dashboard server")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    parser.add_argument("--no-download", action="store_true", help="Skip PDF download when adding a paper")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose / debug output")

    args = parser.parse_args(argv)

    # Dispatch
    if args.list:
        return cmd_list(args.verbose)
    if args.download:
        return cmd_download(args.download, args.verbose)
    if args.open:
        return cmd_open(args.open, args.verbose)
    if args.mark_done:
        return cmd_mark_done(args.mark_done, args.verbose)
    if args.html:
        return cmd_html(args.verbose)
    if args.serve:
        return cmd_server(args.port, args.verbose)
    if args.url:
        return cmd_add(args.url, no_download=args.no_download, verbose=args.verbose)

    # No args — show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
