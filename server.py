"""
LitManager - Flat-tag AI-powered literature management.
MIT License
"""
import http.server
import json
import os
import re
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# When bundled by PyInstaller, use the exe's directory instead of __file__
if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
    # Data files for frozen builds are also in this directory (copied by build script)
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()
DB_PATH = SCRIPT_DIR / "papers.json"
CONFIG_PATH = SCRIPT_DIR / "config.json"
PDF_DIR = SCRIPT_DIR / "pdfs"
PDF_DIR.mkdir(exist_ok=True)
PORT = 8766
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

# In-memory caches with lock
_db_cache = None
_db_lock = threading.Lock()


def load_db():
    global _db_cache
    with _db_lock:
        if _db_cache is not None:
            return _db_cache
        if DB_PATH.exists():
            with open(DB_PATH, "r", encoding="utf-8") as f:
                _db_cache = json.load(f)
        else:
            _db_cache = {"papers": []}
        return _db_cache


def save_db(db):
    global _db_cache
    with _db_lock:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        _db_cache = db


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"base_url": "", "api_key": "", "model": "deepseek-chat"}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def make_ssl_context():
    ctx = ssl.create_default_context()
    return ctx


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    ctx = make_ssl_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def extract_doi(url):
    m = re.search(r"/(10\.\d{4,}/[^/?&#]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"(10\.\d{4,}/[^\s]+)", url)
    return m.group(1).rstrip(".") if m else None


def extract_meta(html, name):
    m = re.search(
        r'<meta\s+name="' + re.escape(name) + r'"\s+content="([^"]+)"', html
    )
    return m.group(1) if m else None


def fetch_bibtex(doi):
    try:
        req = urllib.request.Request(
            f"https://dx.doi.org/{doi}",
            headers={**HEADERS, "Accept": "text/bibliography; style=bibtex"},
        )
        ctx = make_ssl_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_arxiv_id(url):
    m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
    return m.group(1) if m else None


def is_arxiv(url):
    return "arxiv.org" in url


def normalize_author_name(name):
    """Convert 'LastName, FirstName' to 'FirstName LastName'."""
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
    return name


def collect_paper(url):
    if url.startswith("10.") and not url.startswith("http"):
        url = "https://doi.org/" + url

    arxiv_id = extract_arxiv_id(url) if is_arxiv(url) else None
    doi = extract_doi(url) if not arxiv_id else None

    if not doi and not arxiv_id:
        return None, "Could not extract DOI or arXiv ID"

    # Check if already in library
    db = load_db()
    for p in db["papers"]:
        if arxiv_id and p.get("arxiv_id") == arxiv_id:
            return p, None
        if doi and p.get("doi") == doi:
            return p, None

    try:
        html, final_url = fetch_url(url)
    except Exception as e:
        return None, f"Fetch failed: {e}"

    title = extract_meta(html, "citation_title")
    authors = re.findall(r'<meta\s+name="citation_author"\s+content="([^"]+)"', html)
    authors = [normalize_author_name(a) for a in authors]
    journal = extract_meta(html, "citation_journal_title")
    pub_date = extract_meta(html, "citation_date")
    pdf_url_meta = extract_meta(html, "citation_pdf_url")
    abstract = extract_meta(html, "citation_abstract")
    bibtex = fetch_bibtex(doi) if doi else None

    pid = arxiv_id if arxiv_id else doi.split("/")[-1]

    if arxiv_id:
        pdf_default = f"https://arxiv.org/pdf/{arxiv_id}"
        if not journal:
            journal = "arXiv"
    else:
        pdf_default = f"https://journals.aps.org/prb/pdf/{doi}"

    year = pub_date.split("/")[0] if pub_date else ""

    paper = {
        "id": pid,
        "title": title or "Unknown",
        "authors": authors or [],
        "journal": journal or "",
        "doi": doi or "",
        "url": final_url,
        "pdf_url": pdf_url_meta or pdf_default,
        "bibtex": bibtex or "",
        "abstract": abstract or "",
        "year": year,
        "added": str(date.today()),
        "tags": [],
        "pdf_downloaded": False,
        "arxiv_id": arxiv_id,
    }

    if bibtex:
        for fld, key in [("volume", "volume"), ("number", "issue"), ("pages", "pages")]:
            m = re.search(rf"{fld}\s*=\s*\{{([^}}]+)\}}", bibtex)
            if m:
                paper[key] = m.group(1)

    return paper, None


def rename_pdf(paper):
    pid = paper.get("id", "")
    old = PDF_DIR / f"{pid}.pdf"
    if not old.exists():
        return
    author = (
        paper.get("authors", ["Unknown"])[0] if paper.get("authors") else "Unknown"
    )
    author = author.split(",")[0].strip()
    year = paper.get("year", "")
    title = (
        paper.get("title", "paper")[:40]
        .replace(":", "")
        .replace("/", "")
        .replace("?", "")
        .strip()
    )
    safe = f"{author}_{year}_{title}.pdf".replace(" ", "_")
    new = PDF_DIR / safe
    if new.exists():
        return
    try:
        old.rename(new)
        paper["pdf_local"] = str(new)
        db = load_db()
        for p in db["papers"]:
            if p.get("id") == pid:
                p["pdf_local"] = str(new)
                break
        save_db(db)
        return str(new)
    except OSError:
        pass


def mark_downloaded(paper_id, local_path=None):
    db = load_db()
    for p in db["papers"]:
        if p.get("id") == paper_id:
            p["pdf_downloaded"] = True
            if local_path:
                p["pdf_local"] = local_path
            save_db(db)
            return True
    return False


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fp, ct):
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _safe_read_body(self):
        cl = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(cl) if cl > 0 else b""

    def do_GET(self):
        try:
            p = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(p.query)

            if p.path == "/api/proxy-download":
                remote_url = qs.get("url", [None])[0]
                pid = qs.get("id", [None])[0]
                if not remote_url:
                    self._json({"error": "No url param"}, 400)
                    return
                try:
                    req = urllib.request.Request(remote_url, headers=HEADERS)
                    ctx = make_ssl_context()
                    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                        data = resp.read()
                    if pid:
                        save_path = PDF_DIR / f"{pid}.pdf"
                        with open(save_path, "wb") as f:
                            f.write(data)
                        mark_downloaded(pid, str(save_path))
                        # Rename after save
                        db = load_db()
                        for pp in db["papers"]:
                            if pp.get("id") == pid:
                                rename_pdf(pp)
                                break
                    fn = f"{pid}.pdf" if pid else "paper.pdf"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header(
                        "Content-Disposition", f'attachment; filename="{fn}"'
                    )
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as e:
                    self._json({"error": f"Proxy download failed: {e}"}, 502)
                return

            if p.path == "/api/papers":
                self._json(load_db()["papers"])
                return

            if p.path == "/api/config":
                cfg = load_config()
                safe = dict(cfg)
                k = safe.get("api_key", "")
                if k and len(k) > 8:
                    safe["api_key"] = k[:4] + "****" + k[-4:]
                self._json(safe)
                return

            m = re.match(r"/api/pdf/(.+)", p.path)
            if m:
                fp = PDF_DIR / f"{m.group(1)}.pdf"
                if fp.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header(
                        "Content-Disposition",
                        f'inline; filename="{m.group(1)}.pdf"',
                    )
                    self.end_headers()
                    with open(fp, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self._json({"error": "PDF not found"}, 404)
                return

            # Serve index.html for everything else
            fp = SCRIPT_DIR / "index.html"
            if fp.exists():
                self._file(fp, "text/html; charset=utf-8")
            else:
                self._json({"error": "not found"}, 404)

        except Exception as e:
            try:
                self._json({"error": f"Server error: {e}"}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            body = self._safe_read_body()
            ct = self.headers.get("Content-Type", "")
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)

            # --- /api/fetch-and-save ---
            if parsed.path == "/api/fetch-and-save":
                try:
                    d = json.loads(body.decode("utf-8"))
                    remote_url = d.get("url", "").strip()
                    pid = d.get("id", "").strip()
                    if not remote_url or not pid:
                        self._json({"ok": False, "error": "Need url and id"}, 400)
                        return
                    req = urllib.request.Request(remote_url, headers=HEADERS)
                    ctx = make_ssl_context()
                    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                        data = resp.read()
                    save_path = PDF_DIR / f"{pid}.pdf"
                    with open(save_path, "wb") as f:
                        f.write(data)
                    mark_downloaded(pid, str(save_path))
                    self._json(
                        {
                            "ok": True,
                            "filename": f"{pid}.pdf",
                            "size": len(data),
                        }
                    )
                except urllib.error.HTTPError as e:
                    self._json(
                        {"ok": False, "error": f"Server fetch failed (HTTP {e.code})"},
                        502,
                    )
                except Exception as e:
                    self._json({"ok": False, "error": f"Server fetch failed: {e}"}, 502)
                return

            # --- /api/papers POST (add paper) ---
            if parsed.path == "/api/papers":
                try:
                    d = json.loads(body.decode("utf-8"))
                    url = d.get("url", "").strip()
                    if not url:
                        self._json({"ok": False, "error": "No URL"}, 400)
                        return
                    paper, err = collect_paper(url)
                    if err:
                        self._json({"ok": False, "error": err}, 400)
                        return
                    db = load_db()
                    # Check if already exists
                    found = False
                    for i, pp in enumerate(db["papers"]):
                        if (
                            paper.get("doi")
                            and pp.get("doi") == paper["doi"]
                            or paper.get("arxiv_id")
                            and pp.get("arxiv_id") == paper["arxiv_id"]
                        ):
                            db["papers"][i] = paper
                            found = True
                            break
                    if found:
                        save_db(db)
                        self._json({"ok": True, "paper": paper, "updated": True})
                    else:
                        db["papers"].append(paper)
                        db["papers"].sort(
                            key=lambda x: x.get("added", ""), reverse=True
                        )
                        save_db(db)
                        self._json({"ok": True, "paper": paper, "added": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/papers/update ---
            if parsed.path == "/api/papers/update":
                try:
                    d = json.loads(body.decode("utf-8"))
                    pid = d.get("id", "")
                    db = load_db()
                    for p in db["papers"]:
                        if p.get("id") == pid:
                            for field in ("tags", "notes", "title"):
                                if field in d:
                                    p[field] = d[field]
                            save_db(db)
                            self._json({"ok": True, "paper": p})
                            return
                    self._json({"ok": False, "error": "Paper not found"}, 404)
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/save-pdf ---
            if parsed.path == "/api/save-pdf":
                pid = qs.get("id", [None])[0]
                if "multipart/form-data" in ct:
                    boundary_marker = ct.split("boundary=")
                    if len(boundary_marker) > 1:
                        boundary = boundary_marker[1].encode()
                        parts = body.split(b"--" + boundary)
                        for part in parts:
                            if b"filename=" in part:
                                header_end = part.find(b"\r\n\r\n")
                                if header_end == -1:
                                    header_end = part.find(b"\n\n")
                                if header_end > 0:
                                    pdf_data = part[header_end + 4 :]
                                    # Strip trailing boundary markers but not content
                                    pdf_data = pdf_data.rstrip(b"\r\n-")
                                    fn = f"{pid}.pdf" if pid else "paper.pdf"
                                    with open(PDF_DIR / fn, "wb") as f:
                                        f.write(pdf_data)
                                    if pid:
                                        mark_downloaded(pid, str(PDF_DIR / fn))
                                    self._json(
                                        {
                                            "ok": True,
                                            "filename": fn,
                                            "size": len(pdf_data),
                                        }
                                    )
                                    return
                # Fallback: raw body
                if pid and len(body) > 500:
                    fn = f"{pid}.pdf"
                    with open(PDF_DIR / fn, "wb") as f:
                        f.write(body)
                    mark_downloaded(pid, str(PDF_DIR / fn))
                    self._json(
                        {"ok": True, "filename": fn, "size": len(body)}
                    )
                    return
                self._json({"ok": False, "error": "Parse failed"}, 400)
                return

            # --- /api/chat ---
            if parsed.path == "/api/chat":
                try:
                    d = json.loads(body.decode("utf-8"))
                    msgs = d.get("messages", [])
                    if not msgs:
                        self._json({"ok": False, "error": "No messages"}, 400)
                        return
                    cfg = load_config()
                    bu = cfg.get("base_url", "").strip()
                    ak = cfg.get("api_key", "").strip()
                    md = cfg.get("model", "deepseek-chat").strip()
                    if not bu or not ak:
                        self._json(
                            {"ok": False, "error": "API not configured"}, 400
                        )
                        return
                    api_url = bu.rstrip("/") + "/chat/completions"
                    payload = json.dumps(
                        {"model": md, "messages": msgs, "stream": False}
                    ).encode("utf-8")
                    req = urllib.request.Request(api_url, data=payload, method="POST")
                    req.add_header("Content-Type", "application/json")
                    req.add_header("Authorization", f"Bearer {ak}")
                    req.add_header("User-Agent", "LitManager/1.0")
                    ctx = make_ssl_context()
                    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                    choices = result.get("choices", [])
                    if choices:
                        self._json(
                            {"ok": True, "message": choices[0].get("message", {})}
                        )
                    else:
                        self._json({"ok": False, "error": "No response"}, 500)
                except urllib.error.HTTPError as e:
                    eb = e.read().decode("utf-8", errors="replace")
                    self._json(
                        {"ok": False, "error": f"API Error ({e.code}): {eb[:300]}"},
                        502,
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/config ---
            if parsed.path == "/api/config":
                try:
                    d = json.loads(body.decode("utf-8"))
                    cfg = load_config()
                    if "base_url" in d:
                        cfg["base_url"] = d["base_url"]
                    if "api_key" in d and d["api_key"]:
                        cfg["api_key"] = d["api_key"]
                    if "model" in d:
                        cfg["model"] = d["model"]
                    save_config(cfg)
                    safe = dict(cfg)
                    k = safe.get("api_key", "")
                    if k and len(k) > 8:
                        safe["api_key"] = k[:4] + "****" + k[-4:]
                    self._json({"ok": True, "config": safe})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/papers/delete ---
            if parsed.path == "/api/papers/delete":
                try:
                    d = json.loads(body.decode("utf-8"))
                    pid = d.get("id", "")
                    db = load_db()
                    db["papers"] = [p for p in db["papers"] if p.get("id") != pid]
                    save_db(db)
                    pdf_fp = PDF_DIR / f"{pid}.pdf"
                    if pdf_fp.exists():
                        pdf_fp.unlink()
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            self._json({"error": "not found"}, 404)

        except Exception as e:
            try:
                self._json({"error": f"Server error: {e}"}, 500)
            except Exception:
                pass


def main():
    import webbrowser

    # Try ports in order, in case the default is already in use
    ports = [PORT, 8767, 8768, 8769, 8770]
    server = None
    used_port = None

    for p in ports:
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", p), Handler)
            server.allow_reuse_address = True
            used_port = p
            break
        except OSError:
            continue

    if server is None:
        print("ERROR: Could not bind to any port. Tried:", ", ".join(str(p) for p in ports))
        input("Press Enter to exit...")
        return

    url = f"http://127.0.0.1:{used_port}"
    print("")
    print("  ============================================")
    print(f"   LitManager  |  {url}")
    print(f"   PDFs: {PDF_DIR}")
    if used_port != PORT:
        print(f"   (Port {PORT} was in use, using {used_port} instead)")
    print(f"   Press Ctrl+C to stop")
    print("  ============================================")
    print("")

    # Auto-open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
