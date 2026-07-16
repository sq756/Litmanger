"""HTML dashboard generation — uses a proper template with clean variable substitution."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import PaperDB

logger = logging.getLogger("litmanger.template")

# ── Inline template (also serves as the source for the /install page) ─

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Litmanger — Paper Library</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root { color-scheme: light dark; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f5f5f7;
  color: #1d1d1f;
  line-height: 1.6;
}
.header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%);
  color: white;
  padding: 2.5rem 2rem 1.8rem;
}
.header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.025em; }
.header .subtitle { opacity: 0.65; font-size: 0.8rem; margin-top: 0.2rem; font-family: "SF Mono", "Fira Code", monospace; }
.stats { display: flex; gap: 2.5rem; margin-top: 1.2rem; font-size: 0.85rem; opacity: 0.9; flex-wrap: wrap; }
.stat-value { font-size: 2rem; font-weight: 700; display: block; line-height: 1.1; }
.container { max-width: 1100px; margin: 0 auto; padding: 1.5rem 2rem; }
.controls { display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: center; }
#search { flex: 1; min-width: 220px; padding: 0.65rem 1rem; border: 1px solid #d1d1d6; border-radius: 8px; font-size: 0.95rem; outline: none; background: white; }
#search:focus { border-color: #0f3460; box-shadow: 0 0 0 3px rgba(15,52,96,0.1); }
.btn { padding: 0.6rem 1.2rem; border: none; border-radius: 8px; font-size: 0.85rem; cursor: pointer; font-weight: 500; transition: all 0.15s; text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem; }
.btn-primary { background: #0f3460; color: white; }
.btn-primary:hover { background: #1a4a7a; }
.btn-outline { background: white; color: #0f3460; border: 1px solid #d1d1d6; }
.btn-outline:hover { background: #f5f5fa; border-color: #0f3460; }
.btn-small { padding: 0.35rem 0.7rem; font-size: 0.78rem; border-radius: 6px; }
.paper-card { background: white; border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.06); transition: box-shadow 0.15s; cursor: pointer; border: 1px solid transparent; }
.paper-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: #e5e5ea; }
.paper-card.expanded { box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-color: #d1d1d6; }
.paper-title { font-size: 1.05rem; font-weight: 600; color: #1d1d1f; margin-bottom: 0.3rem; }
.paper-meta { font-size: 0.82rem; color: #666; display: flex; flex-wrap: wrap; gap: 0.3rem 1.2rem; }
.journal { color: #0f3460; font-weight: 500; }
.paper-actions { display: flex; gap: 0.4rem; margin-top: 0.7rem; flex-wrap: wrap; }
.paper-detail { display: none; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e5e5ea; }
.paper-card.expanded .paper-detail { display: block; }
.bibtex-box { background: #f8f8fa; border-radius: 8px; padding: 1rem; font-family: "SF Mono", "Fira Code", "Consolas", monospace; font-size: 0.75rem; white-space: pre-wrap; overflow-x: auto; max-height: 260px; overflow-y: auto; }
.abstract-box { color: #555; font-size: 0.88rem; margin-bottom: 1rem; line-height: 1.7; }
.detail-header { font-size: 0.75rem; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.4rem; margin-top: 1rem; font-weight: 600; }
.empty-state { text-align: center; padding: 3rem; color: #999; }
.empty-state h2 { font-size: 1.1rem; margin-bottom: 0.4rem; font-weight: 500; }
.empty-state p { font-size: 0.88rem; }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 10px; font-size: 0.72rem; font-weight: 500; white-space: nowrap; }
.badge-pdf { background: #e8f5e9; color: #2e7d32; }
.badge-no-pdf { background: #fff3e0; color: #e65100; }
.toast { position: fixed; bottom: 2rem; right: 2rem; background: #1d1d1f; color: white; padding: 0.7rem 1.4rem; border-radius: 8px; font-size: 0.85rem; opacity: 0; transform: translateY(8px); transition: all 0.25s; z-index: 1000; pointer-events: none; }
.toast.show { opacity: 1; transform: translateY(0); }
.quick-add { background: white; border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
.quick-add input { flex: 1; min-width: 280px; padding: 0.65rem 1rem; border: 1px solid #d1d1d6; border-radius: 8px; font-size: 0.9rem; outline: none; background: white; }
.quick-add input:focus { border-color: #0f3460; box-shadow: 0 0 0 3px rgba(15,52,96,0.1); }

@media (prefers-color-scheme: dark) {
  body { background: #1c1c1e; color: #e5e5ea; }
  .header { background: linear-gradient(135deg, #0d0d16 0%, #111a2b 40%, #0a1f38 100%); }
  .paper-card { background: #2c2c2e; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
  .paper-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
  .paper-title { color: #e5e5ea; }
  .paper-meta { color: #a1a1aa; }
  .journal { color: #6ba3d6; }
  .bibtex-box { background: #3a3a3c; }
  .abstract-box { color: #c7c7cc; }
  #search, .quick-add input { background: #3a3a3c; color: #e5e5ea; border-color: #545458; }
  .btn-outline { background: #2c2c2e; color: #6ba3d6; border-color: #545458; }
  .btn-outline:hover { background: #3a3a3c; }
  .quick-add { background: #2c2c2e; }
  .empty-state { color: #8e8e93; }
  .badge-pdf { background: #1b3a1b; color: #4caf50; }
  .badge-no-pdf { background: #3a2a1a; color: #ff9800; }
}
</style>
</head>
<body>

<div class="header">
  <div class="container">
    <h1>Litmanger</h1>
    <div class="subtitle">${pdf_dir}</div>
    <div class="stats">
      <div><span class="stat-value" id="totalCount">${total}</span> papers</div>
      <div><span class="stat-value" id="pdfCount">${pdf_count}</span> PDFs</div>
      <div><span class="stat-value" id="yearRange">${year_range}</span> year range</div>
    </div>
  </div>
</div>

<div class="container">
  <div class="quick-add">
    <span style="font-weight:600;white-space:nowrap;font-size:0.9rem">Add Paper:</span>
    <input type="url" id="urlInput" placeholder="Paste DOI or journal URL, press Enter"
           onkeydown="if(event.key==='Enter')quickAdd()">
    <button class="btn btn-primary" onclick="quickAdd()">Add</button>
    <a class="btn btn-outline" href="/install" style="white-space:nowrap">Setup Guide</a>
  </div>

  <div class="controls">
    <input type="text" id="search" placeholder="Search by title, author, journal, tag…" oninput="renderPapers()">
    <button class="btn btn-outline" onclick="exportAllBibtex()">Export BibTeX</button>
    <button class="btn btn-outline" onclick="location.reload()">Refresh</button>
  </div>

  <div id="paperList"></div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── Data ──────────────────────────────────────────────
const PAPER_DATA = ${papers_json};

// ── Render ────────────────────────────────────────────
function renderPapers() {
  const query = document.getElementById("search").value.toLowerCase();
  const list = document.getElementById("paperList");
  const filtered = PAPER_DATA.filter(p => {
    if (!query) return true;
    const haystack = [
      p.title || "", p.journal || "",
      (p.authors || []).join(" "),
      (p.tags || []).join(" "),
      p.doi || "", p.abstract || ""
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });

  // Stats
  document.getElementById("totalCount").textContent = PAPER_DATA.length;
  document.getElementById("pdfCount").textContent = PAPER_DATA.filter(p => p.pdf_downloaded).length;
  const years = PAPER_DATA.map(p => parseInt(p.year) || 0).filter(y => y > 0);
  if (years.length) {
    const minY = Math.min(...years), maxY = Math.max(...years);
    document.getElementById("yearRange").textContent = minY === maxY ? String(maxY) : minY + "–" + maxY;
  }

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state"><h2>No papers found</h2><p>Try a different search or add a paper above.</p></div>';
    return;
  }

  list.innerHTML = filtered.map((p, i) => {
    const authors = (p.authors || []).slice(0, 5).join(", ") + ((p.authors || []).length > 5 ? " et al." : "");
    const volPages = [p.volume ? "Vol. " + p.volume : "", p.pages].filter(Boolean).join(", ");
    const pdfUrl = p.pdf_url || p.url || "";
    const hasPdf = p.pdf_downloaded;
    return '<div class="paper-card" id="card-' + i + '" onclick="toggleCard(' + i + ')">'
      + '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.75rem">'
      + '<div style="flex:1;min-width:0">'
      + '<div class="paper-title">' + esc(p.title || "Unknown") + '</div>'
      + '<div class="paper-meta">'
      + '<span>' + esc(authors || "Unknown") + '</span>'
      + (p.journal ? '<span class="journal">' + esc(p.journal) + '</span>' : '')
      + (p.year ? '<span>' + esc(String(p.year)) + '</span>' : '')
      + (volPages ? '<span>' + esc(volPages) + '</span>' : '')
      + '</div></div>'
      + '<span class="badge ' + (hasPdf ? "badge-pdf" : "badge-no-pdf") + '">' + (hasPdf ? "PDF" : "No PDF") + '</span>'
      + '</div>'
      + '<div class="paper-actions" onclick="event.stopPropagation()">'
      + (pdfUrl ? '<a class="btn btn-primary btn-small" href="' + escAttr(pdfUrl) + '" target="_blank" rel="noopener">View PDF</a>' : '')
      + '<button class="btn btn-outline btn-small" onclick="copyBibtex(' + i + ')">Copy BibTeX</button>'
      + (p.doi ? '<a class="btn btn-outline btn-small" href="https://doi.org/' + escAttr(p.doi) + '" target="_blank" rel="noopener">DOI</a>' : '')
      + '</div>'
      + '<div class="paper-detail" onclick="event.stopPropagation()">'
      + (p.abstract ? '<div class="detail-header">Abstract</div><div class="abstract-box">' + esc(p.abstract) + '</div>' : '')
      + '<div class="detail-header">BibTeX</div>'
      + '<div class="bibtex-box" id="bibtex-' + i + '">' + esc(p.bibtex || "Not available") + '</div>'
      + ((p.tags || []).length ? '<div class="detail-header">Tags</div><div>' + (p.tags || []).map(t => '<span class="badge" style="background:#e8eaf6;color:#3949ab;margin-right:0.3rem">' + esc(t) + '</span>').join("") + '</div>' : '')
      + '</div></div>';
  }).join("");
}

// ── Helpers ───────────────────────────────────────────
function esc(s) { return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function escAttr(s) { return String(s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }
function toggleCard(i) { document.getElementById("card-" + i)?.classList.toggle("expanded"); }
function copyBibtex(i) {
  const el = document.getElementById("bibtex-" + i);
  if (el) navigator.clipboard.writeText(el.textContent).then(() => showToast("BibTeX copied!")).catch(() => {});
}
function exportAllBibtex() {
  const all = PAPER_DATA.map(p => p.bibtex || "").filter(Boolean).join("\n\n");
  if (!all) { showToast("No BibTeX entries"); return; }
  const blob = new Blob([all], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = "papers.bib"; a.click();
  URL.revokeObjectURL(url);
  showToast("Exported " + PAPER_DATA.filter(p => p.bibtex).length + " entries");
}

// ── Quick-add (copies CLI command) ────────────────────
function quickAdd() {
  const url = document.getElementById("urlInput").value.trim();
  if (!url) { showToast("Paste a URL or DOI first"); return; }
  // Try server-side add first
  fetch("/api/add?url=" + encodeURIComponent(url), { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        showToast("Paper added: " + (data.title || "OK"));
        setTimeout(() => location.reload(), 1200);
      } else {
        showToast("Server add failed — see terminal");
      }
    })
    .catch(() => {
      // Fallback: copy CLI command
      navigator.clipboard.writeText('python -m litmanger "' + url + '"').then(() => {
        document.getElementById("urlInput").value = "";
        showToast("Command copied! Paste in terminal to add.");
      });
    });
}

// ── Toast ─────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 3000);
}

// ── Init ──────────────────────────────────────────────
renderPapers();
</script>
</body>
</html>"""


def generate_html(db: PaperDB, pdf_dir: Path) -> str:
    """Generate the dashboard HTML with paper data embedded."""
    papers = db.papers
    papers_json = json.dumps(
        [p.to_dict() for p in papers],
        indent=2,
        ensure_ascii=False,
    )

    yr = db.year_range
    if yr is None:
        year_range = "—"
    elif yr[0] == yr[1]:
        year_range = str(yr[0])
    else:
        year_range = f"{yr[0]}–{yr[1]}"

    return (
        TEMPLATE.replace("${papers_json}", papers_json)
        .replace("${total}", str(db.count))
        .replace("${pdf_count}", str(db.pdf_count))
        .replace("${year_range}", year_range)
        .replace("${pdf_dir}", str(pdf_dir))
    )


def save_html(db: PaperDB, pdf_dir: Path, output_path: Path) -> Path:
    """Generate and write the static HTML dashboard to disk."""
    html = generate_html(db, pdf_dir)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML dashboard written: %s", output_path)
    return output_path
