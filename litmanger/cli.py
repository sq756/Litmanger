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
        description="Academic paper manager — collect metadata and PDFs from journal URLs.\n"
                    "Subcommands: list, server, add, download, open, mark-done, html\n"
                    "Or just pass a URL directly: litmanger <url>",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  litmanger https://journals.aps.org/prb/abstract/10.1103/PhysRevB.113.235157
  litmanger list
  litmanger server
  litmanger download PhysRevB.113.235157
""",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose / debug output")

    sub = parser.add_subparsers(dest="command", title="commands")
    sub.required = False

    # litmanger add <url>
    add_p = sub.add_parser("add", help="Add a paper from URL or DOI", aliases=["a"])
    add_p.add_argument("url", help="Journal URL or DOI")
    add_p.add_argument("--no-download", action="store_true", help="Skip PDF download")

    # litmanger list
    sub.add_parser("list", help="List all papers", aliases=["ls", "l"])

    # litmanger server
    server_p = sub.add_parser("server", help="Start local dashboard server", aliases=["srv"])
    server_p.add_argument("--port", "-p", type=int, default=8765, help="Port (default: 8765)")

    # litmanger download <id>
    dl_p = sub.add_parser("download", help="Download PDF for a paper", aliases=["dl", "d"])
    dl_p.add_argument("id", metavar="ID", help="Paper ID")

    # litmanger open <id>
    open_p = sub.add_parser("open", help="Open paper in browser")
    open_p.add_argument("id", metavar="ID", help="Paper ID")

    # litmanger mark-done <id>
    md_p = sub.add_parser("mark-done", help="Mark PDF as downloaded")
    md_p.add_argument("id", metavar="ID", help="Paper ID")

    # litmanger html
    sub.add_parser("html", help="Generate static HTML dashboard")

    # Parse
    args, remaining = parser.parse_known_args(argv)

    verbose = args.verbose

    # ── Dispatch by subcommand ──
    cmd = args.command

    if cmd in ("add", "a"):
        return cmd_add(args.url, no_download=args.no_download, verbose=verbose)

    if cmd in ("list", "ls", "l"):
        return cmd_list(verbose)

    if cmd in ("server", "srv"):
        return cmd_server(args.port, verbose)

    if cmd in ("download", "dl", "d"):
        return cmd_download(args.id, verbose)

    if cmd == "open":
        return cmd_open(args.id, verbose)

    if cmd == "mark-done":
        return cmd_mark_done(args.id, verbose)

    if cmd == "html":
        return cmd_html(verbose)

    # ── No subcommand matched — treat first positional as URL ──
    reserved = {"add", "a", "list", "ls", "l", "server", "srv", "download", "dl", "d", "open", "mark-done", "html", "help"}
    for token in (remaining or argv or []):
        if token and not token.startswith("-") and token not in reserved:
            return cmd_add(token, verbose=verbose)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
