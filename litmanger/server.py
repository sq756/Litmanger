"""Local HTTP server — dashboard, API, PDF serving, and browser-side PDF saving.

Binds to 127.0.0.1 only — never exposed to the network."""

from __future__ import annotations

import http.server
import json
import logging
import re
import threading
import urllib.parse
from pathlib import Path

from .fetcher import collect_paper
from .models import PaperDB
from .templates import generate_html

logger = logging.getLogger("litmanger.server")

PORT = 8765


# ══════════════════════════════════════════════════════════
#  Handler
# ══════════════════════════════════════════════════════════


def _create_handler(
    db: PaperDB,
    pdf_dir: Path,
    script_dir: Path,
) -> type[http.server.BaseHTTPRequestHandler]:

    class _Handler(http.server.BaseHTTPRequestHandler):
        """Request handler — one instance per request."""

        # Silence access logs
        def log_message(self, format, *args):
            pass

        # ── GET ───────────────────────────────────────

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            try:
                # API: list papers
                if path == "/api/papers":
                    return self._send_json([p.to_dict() for p in db.papers])

                # API: single paper
                m = re.match(r"^/api/papers/(.+)$", path)
                if m:
                    paper = db.find_by_id(m.group(1))
                    if paper:
                        return self._send_json(paper.to_dict())
                    return self._send_json({"error": "not found"}, 404)

                # API: mark PDF as downloaded
                if path == "/api/mark-downloaded":
                    pid = qs.get("id", [None])[0]
                    if pid:
                        local = str(pdf_dir / (pid + ".pdf"))
                        if db.mark_pdf(pid, local):
                            db.save()
                            return self._send_json({"ok": True})
                    return self._send_json({"ok": False}, 404)

                # Serve PDF files safely
                if path.startswith("/pdfs/"):
                    return self._serve_pdf(path)

                # Serve papers.json (for external tools)
                if path == "/papers.json":
                    return self._send_file(script_dir / "papers.json", "application/json")

                # Install / setup guide
                if path == "/install":
                    return self._serve_install_page()

                # Serve Tampermonkey script
                if path == "/save-paper.user.js":
                    return self._send_file(
                        script_dir / "static" / "save-paper.user.js",
                        "application/javascript; charset=utf-8",
                    )

                # Serve bookmarklet JS
                if path == "/bookmarklet.js":
                    return self._send_file(
                        script_dir / "static" / "bookmarklet.js",
                        "application/javascript; charset=utf-8",
                    )

                # Default: dashboard
                return self._serve_dashboard()

            except Exception as exc:
                logger.exception("Error handling GET %s", path)
                return self._send_json({"error": str(exc)}, 500)

        # ── POST ──────────────────────────────────────

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            try:
                # Save PDF from browser (bookmarklet / Tampermonkey)
                if path == "/api/save-pdf":
                    return self._handle_save_pdf(qs)

                # Trigger add-paper from the web UI
                if path == "/api/add":
                    url = qs.get("url", [None])[0]
                    if not url:
                        return self._send_json({"ok": False, "error": "no url"}, 400)
                    # Run collection in a background thread
                    result = {"ok": False, "title": None}

                    def _collect():
                        try:
                            paper = collect_paper(url)
                            if paper:
                                db.add(paper)
                                db.save()
                                result["ok"] = True
                                result["title"] = paper.title[:80]
                        except Exception as exc:
                            logger.exception("Background collection failed")
                            result["error"] = str(exc)

                    t = threading.Thread(target=_collect, daemon=True)
                    t.start()
                    t.join(timeout=15)
                    return self._send_json(result)

                return self._send_json({"error": "not found"}, 404)

            except Exception as exc:
                logger.exception("Error handling POST %s", path)
                return self._send_json({"error": str(exc)}, 500)

        # ── OPTIONS (CORS preflight) ──────────────────

        def do_OPTIONS(self):
            self._cors_headers()
            self.send_response(200)
            self.end_headers()

        # ── Internal helpers ──────────────────────────

        def _send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, filepath: Path, content_type: str):
            if filepath.is_file():
                data = filepath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send_json({"error": "not found"}, 404)

        def _serve_pdf(self, path: str):
            """Safely serve a PDF from the pdf_dir — blocks path traversal."""
            fname = urllib.parse.unquote(path[len("/pdfs/"):])
            # Reject if unquoting introduced traversal characters
            if ".." in Path(fname).parts:
                logger.warning("Path traversal attempt blocked (unquoted): %s", fname)
                return self._send_json({"error": "forbidden"}, 403)
            # Normalize and validate — must stay inside pdf_dir
            requested = (pdf_dir / fname).resolve()
            try:
                requested.relative_to(pdf_dir.resolve())
            except ValueError:
                logger.warning("Path traversal attempt blocked: %s", fname)
                return self._send_json({"error": "forbidden"}, 403)

            if requested.is_file() and requested.suffix.lower() == ".pdf":
                data = requested.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send_json({"error": "not found"}, 404)

        def _serve_dashboard(self):
            html = generate_html(db, pdf_dir)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_install_page(self):
            """Generate an install/config guide page dynamically."""
            install_html = _build_install_page(script_dir)
            body = install_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_save_pdf(self, qs: dict):
            ct = self.headers.get("Content-Type", "")
            cl = int(self.headers.get("Content-Length", 0))
            if cl == 0:
                return self._send_json({"ok": False, "error": "empty body"}, 400)

            body = self.rfile.read(cl)
            pid = qs.get("id", [None])[0]

            data = None

            # Multipart form upload
            if "multipart/form-data" in ct:
                boundary = ct.split("boundary=")[1].encode() if "boundary=" in ct else None
                if boundary:
                    for part in body.split(b"--" + boundary):
                        if b"filename=" not in part:
                            continue
                        # Find end of headers
                        idx = part.find(b"\r\n\r\n")
                        if idx == -1:
                            idx = part.find(b"\n\n")
                        data = part[idx + 4:].rstrip(b"\r\n") if idx > 0 else part
                        break

            # Raw PDF body
            if data is None and pid and len(body) > 1000 and body[:4] == b"%PDF":
                data = body

            if data is None:
                return self._send_json({"ok": False, "error": "not a PDF"}, 400)

            filename = (pid or "paper") + ".pdf"
            save_path = pdf_dir / filename
            save_path.write_bytes(data)

            if pid:
                db.mark_pdf(pid, str(save_path))
                db.save()

            logger.info("PDF saved via browser: %s (%d KB)", filename, len(data) // 1024)
            return self._send_json({"ok": True, "filename": filename, "size": len(data)})

        def _cors_headers(self):
            # Tight CORS — only allow the local server itself
            origin = self.headers.get("Origin", "")
            self.send_header("Access-Control-Allow-Origin", origin if "localhost" in origin or "127.0.0.1" in origin else "http://localhost:" + str(PORT))
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    return _Handler


# ══════════════════════════════════════════════════════════
#  Install page
# ══════════════════════════════════════════════════════════


def _build_install_page(script_dir: Path) -> str:
    """Build a self-contained install/configuration guide."""
    # Read bookmarklet source
    bm_path = script_dir / "static" / "bookmarklet.js"
    bookmarklet_src = ""
    if bm_path.is_file():
        raw = bm_path.read_text(encoding="utf-8")
        # URL-encode for bookmarklet href
        import urllib.parse

        bookmarklet_src = urllib.parse.quote(raw.strip(), safe="")

    server_url = f"http://localhost:{PORT}"
    pdf_dir = str(script_dir / "pdfs")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Litmanger — Setup</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f7;color:#1d1d1f;line-height:1.7;padding:2rem;max-width:780px;margin:0 auto}}
h1{{font-size:1.8rem;margin-bottom:1rem;color:#0f3460}}
h2{{font-size:1.2rem;margin:2rem 0 0.8rem;color:#333;border-bottom:2px solid #0f3460;padding-bottom:0.3rem;display:inline-block}}
.card{{background:white;border-radius:10px;padding:1.5rem 2rem;margin:1.25rem 0;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
.bookmarklet-link{{display:inline-block;background:linear-gradient(135deg,#0f3460,#1a4a7a);color:white;padding:14px 36px;border-radius:30px;font-size:17px;font-weight:700;text-decoration:none;cursor:grab;margin:1rem 0;box-shadow:0 4px 15px rgba(15,52,96,0.4);user-select:none}}
.bookmarklet-link:active{{cursor:grabbing}}
.steps{{padding-left:1.5rem}}
.steps li{{margin-bottom:0.7rem}}
code{{background:#f0f0f5;padding:0.15rem 0.4rem;border-radius:4px;font-size:0.88em}}
.cmd{{background:#2d2d2d;color:#e0e0e0;padding:0.7rem 1.2rem;border-radius:8px;font-family:"SF Mono","Consolas",monospace;font-size:0.82rem;margin:0.5rem 0;line-height:1.6}}
.tag{{display:inline-block;padding:0.2rem 0.6rem;border-radius:10px;font-size:0.72rem;font-weight:600}}
.tag-green{{background:#e8f5e9;color:#2e7d32}}
.tag-blue{{background:#e8eaf6;color:#3949ab}}
.note{{background:#fff8e1;border-left:4px solid #ffc107;padding:1rem;border-radius:0 8px 8px 0;margin:1rem 0}}
@media(prefers-color-scheme:dark){{body{{background:#1c1c1e;color:#e5e5ea}}h2{{color:#ccc}}code{{background:#3a3a3c;color:#e5e5ea}}.card{{background:#2c2c2e}}}}
</style>
</head>
<body>

<h1>Litmanger Setup</h1>

<div class="note">
  <strong>How it works:</strong> Browse a journal page → click the bookmarklet or floating button
  → PDF is fetched using your browser's institutional login cookies
  → saved directly to <code>pdfs/</code> folder. No more manual Ctrl+S.
</div>

<h2>Step 1: Start the server</h2>
<div class="card">
  <p>Keep this terminal open while you work:</p>
  <div class="cmd">cd "{script_dir}"<br>python -m litmanger server</div>
  <p style="margin-top:0.8rem">Dashboard: <code>{server_url}</code></p>
  <p><span class="tag tag-green">Status</span> <span id="serverStatus">checking...</span></p>
</div>

<h2>Step 2: Install the bookmarklet</h2>
<div class="card">
  <p>Drag this button to your bookmarks bar:</p>
  <a class="bookmarklet-link" href="javascript:{bookmarklet_src}">Save PDF to Litmanger</a>
  <p style="margin-top:0.5rem;color:#888;font-size:0.88rem">
    Bookmark bar hidden? Press <code>Ctrl+Shift+B</code> (Chrome/Edge) or right-click the toolbar → Bookmarks bar → Always show.
  </p>
  <p><strong>Usage:</strong> On any journal paper page, click "Save PDF to Litmanger" → done.</p>
</div>

<h2>Step 3 (optional): Tampermonkey script</h2>
<div class="card">
  <p>Auto-injects floating <span class="tag tag-blue">Save PDF</span> + <span class="tag tag-blue">+ Library</span> buttons.</p>
  <ol class="steps">
    <li>Install <a href="https://www.tampermonkey.net/" target="_blank">Tampermonkey</a></li>
    <li>Open <a href="/save-paper.user.js">save-paper.user.js</a> → Tampermonkey will prompt to install</li>
    <li>Now any APS / arXiv / Nature page will show floating buttons</li>
  </ol>
</div>

<h2>Command-line usage</h2>
<div class="card">
  <p>Add papers from the terminal:</p>
  <div class="cmd">python -m litmanger &lt;url&gt;          # Add paper + auto-download PDF<br>python -m litmanger --list         # List all papers<br>python -m litmanger --html         # Generate static HTML<br>python -m litmanger --download &lt;id&gt; # Re-download PDF<br>python -m litmanger server         # Start dashboard</div>
  <p style="margin-top:0.6rem;font-size:0.88rem;color:#666">PDFs are stored in: <code>{pdf_dir}</code></p>
</div>

<script>
fetch("{server_url}/api/papers")
  .then(r => r.json())
  .then(papers => {{
    document.getElementById("serverStatus").innerHTML =
      '<span style="color:#4caf50;font-weight:600">✓ Server running — ' + papers.length + ' papers</span>';
  }})
  .catch(() => {{
    document.getElementById("serverStatus").innerHTML =
      '<span style="color:#f44336;font-weight:600">✗ Server not running. Start it first.</span>';
  }});
</script>

</body>
</html>"""


# ══════════════════════════════════════════════════════════
#  Server launcher
# ══════════════════════════════════════════════════════════


class ThreadedPaperServer(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer with address reuse."""
    allow_reuse_address = True
    daemon_threads = True


def run_server(
    db: PaperDB,
    pdf_dir: Path,
    script_dir: Path,
    port: int = PORT,
    open_browser: bool = True,
) -> None:
    """Start the Litmanger HTTP server (blocking)."""
    handler = _create_handler(db, pdf_dir, script_dir)

    # Bind to localhost only — never 0.0.0.0
    server = ThreadedPaperServer(("127.0.0.1", port), handler)

    print("\n  Litmanger Server")
    print(f"  Dashboard:  http://127.0.0.1:{port}")
    print(f"  Setup:      http://127.0.0.1:{port}/install")
    print(f"  PDFs:       {pdf_dir}")
    print("  Press Ctrl+C to stop\n")

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
