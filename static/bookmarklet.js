javascript:(function(){
  'use strict';

  var SERVER = 'http://127.0.0.1:8765';
  var MAX_SIZE_MB = 50;

  // ── Extract DOI ────────────────────────────────────
  var url = location.href;
  var doi = '';
  var m = url.match(/\/(10\.\d{4,}\/[^\/?#]+)/);
  if (m) { doi = m[1]; }
  else {
    var metaDoi = document.querySelector('meta[name="citation_doi"]');
    if (metaDoi) doi = metaDoi.content;
  }
  var paperId = doi ? doi.split('/').pop() : 'unknown';

  // ── Find PDF URL ───────────────────────────────────
  var pdfUrl = '';

  // Already on a PDF page
  if (url.indexOf('/pdf/') >= 0 || url.endsWith('.pdf')) {
    pdfUrl = url;
  }
  // citation_pdf_url meta tag
  if (!pdfUrl) {
    var metaPdf = document.querySelector('meta[name="citation_pdf_url"]');
    if (metaPdf && metaPdf.content) pdfUrl = metaPdf.content;
  }
  // Look for PDF links on the page
  if (!pdfUrl) {
    var links = document.querySelectorAll('a[href*="pdf"]');
    for (var i = 0; i < links.length; i++) {
      var href = links[i].href || links[i].getAttribute('href') || '';
      if (href.includes('/pdf/') && href.includes('10.')) {
        pdfUrl = href.startsWith('http') ? href : new URL(href, location.origin).href;
        break;
      }
    }
  }
  // arXiv pattern
  if (!pdfUrl && url.includes('arxiv.org/abs/')) {
    pdfUrl = url.replace('/abs/', '/pdf/');
    if (!pdfUrl.endsWith('.pdf')) pdfUrl += '.pdf';
  }

  if (!pdfUrl) {
    alert('Litmanger: Could not find a PDF URL on this page.');
    return;
  }

  // ── Floating notification ──────────────────────────
  var note = document.createElement('div');
  note.style.cssText = [
    'position:fixed;top:12px;right:12px;z-index:2147483647',
    'background:#0f3460;color:white',
    'padding:10px 20px;border-radius:8px',
    'font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
    'box-shadow:0 4px 16px rgba(0,0,0,.25)',
    'transition:opacity .4s'
  ].join(';');
  note.textContent = 'Saving PDF…';
  document.body.appendChild(note);

  // ── Fetch + save ───────────────────────────────────
  fetch(pdfUrl, { credentials: 'include' })
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var size = parseInt(r.headers.get('Content-Length') || '0');
      if (size > MAX_SIZE_MB * 1024 * 1024) throw new Error('PDF too large (max ' + MAX_SIZE_MB + 'MB)');
      return r.blob();
    })
    .then(function(blob) {
      var fd = new FormData();
      fd.append('pdf', blob, paperId + '.pdf');
      return fetch(SERVER + '/api/save-pdf?id=' + paperId, {
        method: 'POST',
        body: fd
      });
    })
    .then(function(r) { return r.json(); })
    .then(function(j) {
      if (j.ok) {
        note.style.background = '#4caf50';
        note.textContent = '✓ Saved: ' + j.filename + ' (' + (j.size / 1024).toFixed(0) + ' KB)';
      } else {
        note.style.background = '#f44336';
        note.textContent = '✗ Error: ' + (j.error || 'unknown');
      }
    })
    .catch(function(e) {
      note.style.background = '#f44336';
      note.textContent = '✗ Error. Is Litmanger server running?';
      console.error('Litmanger:', e);
    })
    .then(function() {
      setTimeout(function() {
        note.style.opacity = '0';
        setTimeout(function() { note.remove(); }, 500);
      }, 3500);
    });
})();
