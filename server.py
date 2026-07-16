"""
LitManager - Flat-tag AI-powered literature management.
MIT License
"""
import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import shutil
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# ── Import shared utilities from the litmanger package ──
from litmanger.utils import (
    BROWSER_HEADERS,
    extract_doi_from_html,
    extract_meta_name,
    extract_meta_names,
    make_ssl_context,
    normalize_author_name,
)
from litmanger.fetcher import (
    _guess_pdf_url,
    fetch_bibtex,
    fetch_crossref_metadata,
)

# When bundled by PyInstaller, use the exe's directory instead of __file__
if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
    # Data files for frozen builds are also in this directory (copied by build script)
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"
FOLDER_PREF_PATH = SCRIPT_DIR / ".litmanger_folder"
DOWNLOADS_DIR = Path.home() / "Downloads"
PORT = 8766

# In-memory caches with lock
_db_cache = None
_db_lock = threading.Lock()

# ── Path resolvers (lazy, based on user-chosen folder) ──

def _folder_path():
    """Return the user-chosen data folder, defaulting to SCRIPT_DIR."""
    if FOLDER_PREF_PATH.exists():
        try:
            raw = FOLDER_PREF_PATH.read_text("utf-8").strip()
            p = Path(raw)
            if p.is_dir():
                return p
        except Exception:
            pass
    return SCRIPT_DIR


def resolve_pdf_dir():
    """Return the current PDF directory, creating it if needed."""
    p = _folder_path() / "pdfs"
    p.mkdir(exist_ok=True)
    return p


def resolve_db_path():
    return _folder_path() / "papers.json"


def resolve_comments_path():
    return _folder_path() / "comments.json"


def resolve_identity_path():
    return _folder_path() / "identity.json"


def _scan_folder_for_pdfs(folder, db):
    """Scan a folder for PDFs and auto-match to papers in the database.
    Returns a list of matched entries: [{"id": ..., "title": ..., "file": ...}, ...]
    """
    found = []
    for fp in folder.glob("*.pdf"):
        if not fp.is_file():
            continue
        fname = fp.stem.lower().replace(" ", "").replace("(", "").replace(")", "")
        for p in db["papers"]:
            pid = p.get("id", "").lower()
            if pid and pid in fname:
                if not p.get("pdf_downloaded"):
                    normalized = folder / f"{p['id']}.pdf"
                    try:
                        if fp != normalized and fp.exists():
                            shutil.copy2(fp, normalized)
                    except OSError:
                        pass
                    p["pdf_downloaded"] = True
                    p["pdf_local"] = str(normalized)
                    found.append({
                        "id": p["id"],
                        "title": p.get("title", "")[:80],
                        "file": fp.name,
                    })
                break
    return found


def load_db():
    global _db_cache
    with _db_lock:
        if _db_cache is not None:
            return _db_cache
        db_path = resolve_db_path()
        if db_path.exists():
            with open(db_path, "r", encoding="utf-8") as f:
                _db_cache = json.load(f)
        else:
            _db_cache = {"papers": []}
        return _db_cache


def save_db(db):
    global _db_cache
    with _db_lock:
        with open(resolve_db_path(), "w", encoding="utf-8") as f:
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


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    ctx = make_ssl_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def extract_doi(url):
    """Extract DOI from any journal URL or bare DOI string."""
    m = re.search(r"(10\.\d{4,}/[^?&#\"\'\s<>]+)", url)
    if m:
        doi = m.group(1).rstrip(".")
        for suffix in (".abstract", ".full", ".pdf", ".meta"):
            if doi.endswith(suffix):
                doi = doi[:-len(suffix)]
        return doi
    return None


def extract_arxiv_id(url):
    m = re.search(r"arxiv\.org/abs/([\d.]+)", url)
    return m.group(1) if m else None


def is_arxiv(url):
    return "arxiv.org" in url


def collect_paper(url):
    if url.startswith("10.") and not url.startswith("http"):
        url = "https://doi.org/" + url

    arxiv_id = extract_arxiv_id(url) if is_arxiv(url) else None
    doi = extract_doi(url) if not arxiv_id else None

    # Fetch the HTML page (with graceful fallback)
    html = None
    final_url = url
    crossref_meta = None
    try:
        html, final_url = fetch_url(url)
    except Exception:
        pass  # Page blocked (403), try Crossref API below

    # If page fetch failed, get metadata fromCrossref
    if not html and doi:
        crossref_meta = fetch_crossref_metadata(doi)

    # If we have HTML but no DOI yet, extract from HTML
    if html and not doi and not arxiv_id:
        doi = extract_doi_from_html(html) or extract_doi(final_url)

    # arXiv: extract DOI from arxiv-doi-link in HTML
    if arxiv_id and not doi and html:
        m = re.search(r'<a\s+[^>]*href="https?://doi\.org/(10\.\d{4,}/[^"]+)"[^>]*>', html, re.I)
        if m: doi = m.group(1).rstrip(".")

    if not doi and not arxiv_id:
        return None, "Could not extract DOI or arXiv ID"

    # Check if already in library
    db = load_db()
    for p in db["papers"]:
        if arxiv_id and p.get("arxiv_id") == arxiv_id: return p, None
        if doi and p.get("doi") == doi: return p, None

    # Extract metadata
    if html:
        title = extract_meta_namehtml, "citation_title")
        if title:
            title = title.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        authors = [normalize_author_name(a) for a in re.findall(r'<meta\s+name="citation_author"\s+content="([^"]+)"', html)]
        journal = extract_meta_namehtml, "citation_journal_title")
        pub_date = extract_meta_namehtml, "citation_date")
        pdf_url_meta = extract_meta_namehtml, "citation_pdf_url")
        abstract = extract_meta_namehtml, "citation_abstract")
    elif crossref_meta:
        title = crossref_meta.get("title")
        authors = crossref_meta.get("authors", [])
        journal = crossref_meta.get("journal")
        pub_date = None
        pdf_url_meta = crossref_meta.get("pdf_url")
        abstract = crossref_meta.get("abstract")
        if crossref_meta.get("year"):
            pub_date = crossref_meta["year"]
            if crossref_meta.get("month"): pub_date += "/" + crossref_meta["month"]
    else:
        title, authors, journal, pub_date, pdf_url_meta, abstract = "Unknown", [], "", None, None, None

    bibtex = fetch_bibtex(doi) if doi else None
    pid = arxiv_id if arxiv_id else doi.split("/")[-1]

    if arxiv_id:
        pdf_default = f"https://arxiv.org/pdf/{arxiv_id}"
        if not journal: journal = "arXiv"
    else:
        pdf_default = _guess_pdf_url(final_url, doi, html)

    year = pub_date.split("/")[0] if pub_date else ""
    paper = {"id": pid, "title": title or "Unknown", "authors": authors or [], "journal": journal or "",
             "doi": doi or "", "url": final_url, "pdf_url": pdf_url_meta or pdf_default,
             "bibtex": bibtex or "", "abstract": abstract or "", "year": year,
             "added": str(date.today()), "tags": [], "pdf_downloaded": False, "arxiv_id": arxiv_id}

    if bibtex:
        for fld, key in [("volume", "volume"), ("number", "issue"), ("pages", "pages")]:
            m = re.search(rf"{fld}\s*=\s*\{{([^}}]+)\}}", bibtex)
            if m:
                paper[key] = m.group(1)

    return paper, None


def rename_pdf(paper):
    pid = paper.get("id", "")
    old = resolve_pdf_dir() / f"{pid}.pdf"
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
    new = resolve_pdf_dir() / safe
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


def load_comments():
    cpath = resolve_comments_path()
    if cpath.exists():
        with open(cpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_comments(comments):
    with open(resolve_comments_path(), "w", encoding="utf-8") as f:
        json.dump(comments, f, indent=2, ensure_ascii=False)


def load_identity():
    """Load or generate an Ed25519 keypair for this installation."""
    ipath = resolve_identity_path()
    if ipath.exists():
        with open(ipath, "r", encoding="utf-8") as f:
            return json.load(f)
    # Generate new keypair using Python cryptography if available
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization

        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        priv_bytes = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        ident = {
            "pubkey": base64.b64encode(pub_bytes).decode("ascii"),
            "privkey": base64.b64encode(priv_bytes).decode("ascii"),
        }
    except ImportError:
        # Fallback: use python-ecdsa or just generate random identifier
        # Without 'cryptography', we use a hash-based identity (no sig verification)
        seed = secrets.token_bytes(32)
        ident = {
            "pubkey": base64.b64encode(hashlib.sha256(seed).digest()).decode("ascii"),
            "seed": base64.b64encode(seed).decode("ascii"),
        }
    with open(resolve_identity_path(), "w", encoding="utf-8") as f:
        json.dump(ident, f, indent=2)
    return ident


def sign_comment_data(data_str):
    """Sign a comment payload. Returns (pubkey_b64, sig_b64) or (None, None)."""
    ident = load_identity()
    pubkey_b64 = ident["pubkey"]
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization

        priv_bytes = base64.b64decode(ident["privkey"])
        priv = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        sig = priv.sign(data_str.encode("utf-8"))
        sig_b64 = base64.b64encode(sig).decode("ascii")
        return pubkey_b64, sig_b64
    except ImportError:
        return None, None


def generate_html_page(db):
    """Generate a static HTML page for offline browsing / sharing."""
    papers = db["papers"]
    rows = []
    for p in papers:
        title = p.get("title", "Unknown")
        authors = ", ".join(p.get("authors", [])[:5])
        if len(p.get("authors", [])) > 5:
            authors += " et al."
        journal = p.get("journal", "")
        year = p.get("year", "")
        doi = p.get("doi", "")
        abstract = (p.get("abstract", "") or "")[:500]
        tags = " ".join(
            f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#eef2ff;color:#4f46e5;margin:2px">{t}</span>'
            for t in p.get("tags", [])
        )
        pdf_ok = "&#x2705;" if p.get("pdf_downloaded") else "&#x274C;"
        rows.append(f"""<tr>
        <td>{pdf_ok}</td>
        <td><strong>{title}</strong><br><small>{authors}</small><br><small>{journal} ({year})</small></td>
        <td>{tags}</td>
        <td><small><a href="https://doi.org/{doi}" target="_blank">{doi}</a></small></td>
        <td><small>{abstract}</small></td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LitManager Paper Library</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f0f1f5;color:#1a1a2e;padding:2rem}}
h1{{margin-bottom:1rem;color:#4f46e5}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th,td{{padding:0.75rem;text-align:left;border-bottom:1px solid #e2e4e9;font-size:0.85rem;line-height:1.5}}
th{{background:#f5f5fa;font-weight:600;font-size:0.78rem;text-transform:uppercase;color:#666}}
tr:hover{{background:#f5f5fa}}
</style>
</head>
<body>
<h1>LitManager Paper Library</h1>
<p style="margin-bottom:1.5rem;color:#666;font-size:0.85rem">{len(papers)} papers &middot; Generated on {date.today().isoformat()}</p>
<table>
<thead><tr><th>PDF</th><th>Title / Authors / Journal</th><th>Tags</th><th>DOI</th><th>Abstract</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body>
</html>"""


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
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fp, ct):
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _safe_read_body(self):
        cl = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(cl) if cl > 0 else b""

    # ── Bookmarklet / Install helpers ──────────────

    def _server_url(self):
        """Return the full origin for this server (http://127.0.0.1:<port>)."""
        host = self.headers.get("Host", f"127.0.0.1:{PORT}")
        scheme = "http"
        return f"{scheme}://{host}"

    def _serve_bookmarklet(self):
        server_url = self._server_url()
        bm_js = rf"""(function(){{
  var SERVER='{server_url}';
  var url=location.href,doi='',pdfUrl='';
  var m=url.match(/\/(10\.\d{{4,}}\/[^\/?#]+)/);
  if(m)doi=m[1];
  else{{var metaDoi=document.querySelector('meta[name="citation_doi"]');if(metaDoi)doi=metaDoi.content}}
  var paperId=doi?doi.split('/').pop():'unknown';
  if(url.indexOf('/pdf/')>=0||url.endsWith('.pdf'))pdfUrl=url;
  if(!pdfUrl){{var metaPdf=document.querySelector('meta[name="citation_pdf_url"]');if(metaPdf&&metaPdf.content)pdfUrl=metaPdf.content}}
  if(!pdfUrl){{var links=document.querySelectorAll('a[href*="pdf"]');for(var i=0;i<links.length;i++){{var href=links[i].href||links[i].getAttribute('href')||'';if(href.includes('/pdf/')&&href.includes('10.')){{pdfUrl=href.startsWith('http')?href:new URL(href,location.origin).href;break}}}}}}
  if(!pdfUrl&&url.includes('arxiv.org/abs/'))pdfUrl=url.replace('/abs/','/pdf/')+'.pdf';
  if(!pdfUrl){{alert('Litmanger: No PDF URL found on this page.');return}}
  var note=document.createElement('div');note.style.cssText='position:fixed;top:12px;right:12px;z-index:2147483647;background:#0f3460;color:#fff;padding:10px 20px;border-radius:8px;font:14px -apple-system,BlinkMacSystemFont,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.25);transition:opacity .4s';note.textContent='Saving PDF...';document.body.appendChild(note);
  fetch(pdfUrl,{{credentials:'include'}}).then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.blob()}}).then(function(blob){{var fd=new FormData();fd.append('pdf',blob,paperId+'.pdf');return fetch(SERVER+'/api/save-pdf?id='+paperId,{{method:'POST',body:fd}})}}).then(function(r){{return r.json()}}).then(function(j){{if(j.ok){{note.style.background='#4caf50';note.textContent='✓ Saved: '+j.filename+' ('+(j.size/1024).toFixed(0)+' KB)'}}else{{note.style.background='#f44336';note.textContent='✗ Error: '+(j.error||'unknown')}}}}).catch(function(e){{note.style.background='#f44336';note.textContent='✗ Error. Is Litmanger running?'}}).then(function(){{setTimeout(function(){{note.style.opacity='0';setTimeout(function(){{note.remove()}},500)}},3500)}});
}})();"""
        body = bm_js.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_install_page(self):
        server_url = self._server_url()
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Litmanger — Setup</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f7;color:#1d1d1f;line-height:1.7;padding:2rem;max-width:780px;margin:0 auto}}
.card{{background:white;border-radius:12px;padding:1.5rem 2rem;margin:1.25rem 0;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
h1{{font-size:1.8rem;margin-bottom:1rem;color:#0f3460}}
h2{{font-size:1.2rem;margin:1.5rem 0 .8rem;color:#333;border-bottom:2px solid #0f3460;padding-bottom:.3rem;display:inline-block}}
.bml{{display:inline-block;background:linear-gradient(135deg,#0f3460,#1a4a7a);color:#fff;padding:14px 36px;border-radius:30px;font-size:17px;font-weight:700;text-decoration:none;cursor:grab;margin:1rem 0;box-shadow:0 4px 15px rgba(15,52,96,.4);user-select:none}}
.bml:active{{cursor:grabbing}}
code{{background:#f0f0f5;padding:.15rem .4rem;border-radius:4px;font-size:.88em}}
.cmd{{background:#2d2d2d;color:#e0e0e0;padding:.7rem 1.2rem;border-radius:8px;font-family:"SF Mono","Consolas",monospace;font-size:.82rem;margin:.5rem 0;line-height:1.6}}
.note{{background:#fff8e1;border-left:4px solid #ffc107;padding:1rem;border-radius:0 8px 8px 0;margin:1rem 0}}
@media(prefers-color-scheme:dark){{body{{background:#1c1c1e;color:#e5e5ea}}h2{{color:#ccc}}code{{background:#3a3a3c;color:#e5e5ea}}.card{{background:#2c2c2e}}}}
</style>
</head>
<body>
<h1>Litmanger Setup</h1>
<div class="note"><strong>How it works:</strong> Browse a journal page → click bookmarklet → PDF is saved directly to <code>pdfs/</code> folder using your browser's login cookies.</div>

<h2>Step 1: Server running?</h2>
<div class="card">
<p>Server URL: <code id="svr">{server_url}</code> <span id="status" style="margin-left:.5rem">checking...</span></p>
<p style="margin-top:.5rem;font-size:.88rem;color:#666">If you don't see the dashboard, run <code>python server.py</code> first.</p>
</div>

<h2>Step 2: Install bookmarklet</h2>
<div class="card">
<p>Drag this button to your bookmarks bar:</p>
<a class="bml" href="javascript:(function(){{var s=document.createElement('script');s.src='{server_url}/bm.js';document.body.appendChild(s)}})()">Save PDF to Litmanger</a>
<p style="margin-top:.5rem;color:#888;font-size:.88rem">Bookmark bar hidden? Press <code>Ctrl+Shift+B</code> (Chrome/Edge).</p>
<p style="margin-top:.5rem"><strong>Usage:</strong> On any journal page, click "Save PDF to Litmanger" in your bookmarks → done.</p>
</div>

<script>
var url='{server_url}';
fetch(url+'/api/papers').then(function(r){{return r.json()}}).then(function(p){{document.getElementById('status').innerHTML='<span style="color:#4caf50;font-weight:600">✓ Running — '+p.length+' papers</span>'}}).catch(function(){{document.getElementById('status').innerHTML='<span style="color:#f44336;font-weight:600">✗ Not running</span>'}});
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
                    req = urllib.request.Request(remote_url, headers=BROWSER_HEADERS)
                    ctx = make_ssl_context()
                    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                        data = resp.read()
                    # Validate it's actually a PDF
                    if data[:100].lstrip().startswith(b"<!DOCTYPE") or data[:100].lstrip().startswith(b"<html"):
                        self._json({"error": "Journal returned HTML instead of PDF (Cloudflare / login wall). Open the PDF URL in your browser to download."}, 502)
                        return
                    if pid and data[:5] == b"%PDF-":
                        save_path = resolve_pdf_dir() / f"{pid}.pdf"
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

            if p.path == "/api/get-folder":
                folder = _folder_path()
                self._json({
                    "path": str(folder),
                    "pdf_dir": str(resolve_pdf_dir()),
                    "has_papers": resolve_db_path().exists(),
                    "is_default": folder == SCRIPT_DIR,
                })
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
                clean_id = m.group(1)
                # Try exact match first
                fp = resolve_pdf_dir() / f"{clean_id}.pdf"
                if not fp.exists():
                    # Try papers.json to find the actual local path
                    db_papers = load_db()
                    for paper in db_papers["papers"]:
                        if paper.get("id") == clean_id and paper.get("pdf_local"):
                            fp = Path(paper["pdf_local"])
                            if fp.exists():
                                break
                    else:
                        # Last resort: find any PDF starting with this ID
                        candidates = sorted(
                            resolve_pdf_dir().glob(f"{clean_id}*.pdf"),
                            key=lambda x: x.stat().st_mtime, reverse=True,
                        )
                        fp = candidates[0] if candidates else None
                if fp and fp.exists():
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

            # --- /api/comments ---
            if p.path == "/api/comments":
                doi = qs.get("doi", [None])[0]
                comments = load_comments()
                self._json(comments.get(doi, []))
                return

            # /install — bookmarklet setup page
            if p.path == "/install":
                self._serve_install_page()
                return

            # /bm.js — dynamic bookmarklet with current server origin
            if p.path == "/bm.js":
                self._serve_bookmarklet()
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

            # --- /api/set-folder ---
            if parsed.path == "/api/set-folder":
                try:
                    d = json.loads(body.decode("utf-8"))
                    new_path_str = d.get("path", "").strip()
                    if not new_path_str:
                        self._json({"ok": False, "error": "No path provided"}, 400)
                        return
                    new_path = Path(new_path_str).resolve()
                    if not new_path.is_dir():
                        self._json({"ok": False, "error": "Path is not a valid directory"}, 400)
                        return
                    FOLDER_PREF_PATH.write_text(str(new_path), encoding="utf-8")
                    pdf_dir = new_path / "pdfs"
                    pdf_dir.mkdir(exist_ok=True)
                    target_db = new_path / "papers.json"
                    old_db = SCRIPT_DIR / "papers.json"
                    migrated = False
                    if not target_db.exists() and old_db.exists():
                        shutil.copy2(old_db, target_db)
                        migrated = True
                    target_comments = new_path / "comments.json"
                    old_comments = SCRIPT_DIR / "comments.json"
                    if not target_comments.exists() and old_comments.exists():
                        shutil.copy2(old_comments, target_comments)
                    target_identity = new_path / "identity.json"
                    old_identity = SCRIPT_DIR / "identity.json"
                    if not target_identity.exists() and old_identity.exists():
                        shutil.copy2(old_identity, target_identity)
                    global _db_cache
                    with _db_lock:
                        _db_cache = None
                    db = load_db()
                    matched = _scan_folder_for_pdfs(pdf_dir, db)
                    if matched:
                        save_db(db)
                    self._json({
                        "ok": True,
                        "path": str(new_path),
                        "pdf_dir": str(pdf_dir),
                        "migrated": migrated,
                        "matched_pdfs": len(matched),
                        "paper_count": len(db["papers"]),
                    })
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/fetch-and-save ---
            if parsed.path == "/api/fetch-and-save":
                try:
                    d = json.loads(body.decode("utf-8"))
                    remote_url = d.get("url", "").strip()
                    pid = d.get("id", "").strip()
                    if not remote_url or not pid:
                        self._json({"ok": False, "error": "Need url and id"}, 400)
                        return
                    req = urllib.request.Request(remote_url, headers=BROWSER_HEADERS)
                    ctx = make_ssl_context()
                    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                        data = resp.read()
                    # Validate: reject HTML responses (Cloudflare / login walls)
                    if data[:100].lstrip().startswith(b"<!DOCTYPE") or data[:100].lstrip().startswith(b"<html"):
                        self._json(
                            {"ok": False, "error": "Journal page returned instead of PDF (Cloudflare / login required). Open in browser to download manually."},
                            502,
                        )
                        return
                    if not data[:5] == b"%PDF-":
                        self._json(
                            {"ok": False, "error": "Response is not a valid PDF file."},
                            502,
                        )
                        return
                    save_path = resolve_pdf_dir() / f"{pid}.pdf"
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
                            for field in ("tags", "notes", "title", "md_notes"):
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
                                    with open(resolve_pdf_dir() / fn, "wb") as f:
                                        f.write(pdf_data)
                                    if pid:
                                        mark_downloaded(pid, str(resolve_pdf_dir() / fn))
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
                    with open(resolve_pdf_dir() / fn, "wb") as f:
                        f.write(body)
                    mark_downloaded(pid, str(resolve_pdf_dir() / fn))
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

            # --- /api/papers/mark-downloaded ---
            if parsed.path == "/api/papers/mark-downloaded":
                try:
                    d = json.loads(body.decode("utf-8"))
                    pid = d.get("id", "")
                    db = load_db()
                    paper_found = None
                    for p in db["papers"]:
                        if p.get("id") == pid:
                            paper_found = p
                            break
                    if not paper_found:
                        self._json({"ok": False, "error": "Paper not found"}, 404)
                        return

                    paper_found["pdf_downloaded"] = True

                    # 1. Check pdfs/ folder first
                    candidates = sorted(
                        [fp for fp in resolve_pdf_dir().glob(f"{pid}*.pdf") if fp.is_file()],
                        key=lambda x: (x.name != f"{pid}.pdf", -x.stat().st_mtime),
                    )

                    # 2. Also check Downloads folder
                    if DOWNLOADS_DIR.exists():
                        for dl in sorted(
                            DOWNLOADS_DIR.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True
                        ):
                            candidates.append(dl)

                    if candidates:
                        best = candidates[0]
                        normalized = resolve_pdf_dir() / f"{pid}.pdf"
                        try:
                            if best != normalized:
                                if best.exists():
                                    import shutil
                                    shutil.copy2(best, normalized)
                                    best = normalized
                        except OSError:
                            pass
                        paper_found["pdf_local"] = str(best.absolute() if best.parent != resolve_pdf_dir() else best)

                    save_db(db)
                    self._json({"ok": True, "paper": paper_found})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/scan-pdfs ---
            if parsed.path == "/api/scan-pdfs":
                try:
                    found = []
                    db = load_db()
                    # Scan pdfs/ and Downloads/
                    all_dirs = [resolve_pdf_dir()]
                    if DOWNLOADS_DIR.exists():
                        all_dirs.append(DOWNLOADS_DIR)
                    for scan_dir in all_dirs:
                        for fp in scan_dir.glob("*.pdf"):
                            if not fp.is_file():
                                continue
                            fname = fp.stem.lower().replace(" ", "").replace("(", "").replace(")", "")
                            matched = None
                            for p in db["papers"]:
                                pid = p.get("id", "").lower()
                                if pid and pid in fname:
                                    matched = p
                                    break
                            if not matched:
                                # Try DOI-based match (last resort: PDF embedded metadata)
                                continue
                            if not matched.get("pdf_downloaded"):
                                normalized = resolve_pdf_dir() / f"{matched['id']}.pdf"
                                try:
                                    import shutil
                                    if fp != normalized and fp.exists():
                                        shutil.copy2(fp, normalized)
                                except OSError:
                                    pass
                                matched["pdf_downloaded"] = True
                                matched["pdf_local"] = str(normalized)
                                found.append({"id": matched["id"], "title": matched.get("title", "")[:80], "file": fp.name})
                    if found:
                        save_db(db)
                    self._json({"ok": True, "matched": found})
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
                    pdf_fp = resolve_pdf_dir() / f"{pid}.pdf"
                    if pdf_fp.exists():
                        pdf_fp.unlink()
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/list-models ---
            if parsed.path == "/api/list-models":
                try:
                    d = json.loads(body.decode("utf-8"))
                    bu = d.get("base_url", "").strip()
                    ak = d.get("api_key", "").strip()
                    if not bu or not ak:
                        self._json({"ok": False, "error": "Need base_url and api_key"}, 400)
                        return
                    models = []
                    from_api = False
                    # Try GET /models endpoint (OpenAI-compatible)
                    try:
                        api_url = bu.rstrip("/") + "/models"
                        req = urllib.request.Request(api_url, method="GET")
                        req.add_header("Authorization", f"Bearer {ak}")
                        req.add_header("User-Agent", "LitManager/1.0")
                        ctx = make_ssl_context()
                        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                            result = json.loads(resp.read().decode("utf-8"))
                        for m in result.get("data", []):
                            mid = m.get("id", "")
                            if mid and not any(skip in mid.lower() for skip in ("embed", "moderat", "audio", "tts", "whisper", "dall", "image", "vision")):
                                models.append(mid)
                        if models:
                            from_api = True
                    except Exception:
                        pass  # Fall back to known models below

                    # If API call failed or returned empty, use known models per provider
                    if not from_api:
                        known = {
                            "deepseek": ["deepseek-chat", "deepseek-reasoner", "deepseek-v3", "deepseek-v4-pro"],
                            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"],
                            "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
                            "ollama": ["llama3", "mistral", "gemma2", "qwen2", "codellama"],
                            "openrouter": ["openai/gpt-4o", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro"],
                            "siliconflow": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct", "Pro/Llama-3.3-70B-Instruct"],
                            "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
                        }
                        host = bu.lower()
                        matched = None
                        for keyword in known:
                            if keyword in host:
                                matched = known[keyword]
                                break
                        if matched:
                            models = matched
                        else:
                            models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "deepseek-chat", "deepseek-reasoner", "claude-sonnet-4-20250514"]

                    # Sort smartly
                    def _score(mid):
                        s = mid.lower()
                        if "chat" in s or "instruct" in s:
                            return 0
                        if "completion" in s or "gpt" in s or "claude" in s or "deepseek" in s or "qwen" in s:
                            return 1
                        return 2
                    models.sort(key=_score)
                    self._json({"ok": True, "models": models, "from_api": from_api})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/generate-html ---
            if parsed.path == "/api/generate-html":
                try:
                    db = load_db()
                    html = generate_html_page(db)
                    html_path = SCRIPT_DIR / "paper_library.html"
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    self._json({"ok": True, "path": str(html_path.name)})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/comments ---
            if parsed.path == "/api/comments":
                try:
                    d = json.loads(body.decode("utf-8"))
                    doi = d.get("doi", "").strip()
                    author = d.get("author", "").strip() or "Anonymous"
                    text = d.get("text", "").strip()
                    if not doi or not text:
                        self._json({"ok": False, "error": "Need doi and text"}, 400)
                        return
                    comments = load_comments()
                    existing = comments.get(doi, [])
                    # Generate a short unique ID (locally unique + timestamp)
                    cid = secrets.token_hex(6)
                    entry = {
                        "id": cid,
                        "author": author,
                        "text": text,
                        "time": date.today().isoformat(),
                    }
                    comments[doi] = existing + [entry]
                    save_comments(comments)
                    self._json({"ok": True, "comments": comments[doi]})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/comments/delete ---
            if parsed.path == "/api/comments/delete":
                try:
                    d = json.loads(body.decode("utf-8"))
                    doi = d.get("doi", "").strip()
                    cid = d.get("id", "").strip()
                    if not doi or not cid:
                        self._json({"ok": False, "error": "Need doi and id"}, 400)
                        return
                    comments = load_comments()
                    existing = comments.get(doi, [])
                    comments[doi] = [c for c in existing if c.get("id") != cid]
                    if not comments[doi]:
                        del comments[doi]
                    save_comments(comments)
                    self._json({"ok": True, "comments": comments.get(doi, [])})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
                return

            # --- /api/sign-comment ---
            if parsed.path == "/api/sign-comment":
                try:
                    d = json.loads(body.decode("utf-8"))
                    ident = load_identity()
                    pubkey_b64 = ident["pubkey"]
                    # Build signature payload: doi|id|author|text|time|pubkey
                    payload = "|".join([
                        d.get("doi", ""),
                        d.get("id", ""),
                        d.get("author", ""),
                        d.get("text", ""),
                        d.get("time", ""),
                        pubkey_b64,
                    ])
                    _, sig_b64 = sign_comment_data(payload)
                    signed = dict(d)
                    signed["pubkey"] = pubkey_b64
                    signed["sig"] = sig_b64
                    self._json({"ok": True, "comment": signed})
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
    print(f"   PDFs: {resolve_pdf_dir()}")
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
