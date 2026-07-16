// ==UserScript==
// @name         Litmanger — One-Click PDF Save
// @namespace    litmanger
// @version      2.0.0
// @description  Auto-injects "Save PDF" and "+ Library" buttons on journal pages.
//               Click to save PDFs directly to your local paper library.
// @author       Litmanger
// @match        https://journals.aps.org/*
// @match        https://link.aps.org/*
// @match        https://arxiv.org/abs/*
// @match        https://arxiv.org/pdf/*
// @match        https://www.nature.com/articles/*
// @match        https://link.springer.com/article/*
// @match        https://onlinelibrary.wiley.com/doi/*
// @match        https://www.sciencedirect.com/science/article/*
// @match        https://iopscience.iop.org/article/*
// @match        https://pubs.acs.org/doi/*
// @match        https://dl.acm.org/doi/*
// @match        https://ieeexplore.ieee.org/document/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// ==/UserScript==

(function() {
  'use strict';

  var SERVER = 'http://127.0.0.1:8765';
  var serverOnline = false;

  // ── Server check ───────────────────────────────────
  function checkServer() {
    return fetch(SERVER + '/api/papers', { mode: 'cors' })
      .then(function(r) { return r.ok; })
      .catch(function() { return false; });
  }

  // ── DOI extraction ─────────────────────────────────
  function getDoi() {
    var url = location.href;
    // DOI in URL path
    var m = url.match(/\/(10\.\d{4,}\/[^\/?#]+)/);
    if (m) return m[1];
    // citation_doi meta
    var meta = document.querySelector('meta[name="citation_doi"]');
    if (meta && meta.content) return meta.content;
    // dc.Identifier
    meta = document.querySelector('meta[name="dc.Identifier"]');
    if (meta && meta.content && meta.content.startsWith('doi:')) return meta.content.slice(4);
    return null;
  }

  function getPaperId() {
    var doi = getDoi();
    return doi ? doi.split('/').pop() : null;
  }

  // ── PDF URL detection ──────────────────────────────
  function getPdfUrl() {
    var url = location.href;

    // Already on a PDF page
    if (url.includes('/pdf/') || url.endsWith('.pdf')) return url;

    // citation_pdf_url meta
    var meta = document.querySelector('meta[name="citation_pdf_url"]');
    if (meta && meta.content) return meta.content;

    // Look for PDF links
    var links = document.querySelectorAll('a[href*="pdf"]');
    for (var i = 0; i < links.length; i++) {
      var href = links[i].href || links[i].getAttribute('href') || '';
      if (href.includes('/pdf/') && /10\./.test(href)) {
        return href.startsWith('http') ? href : new URL(href, location.origin).href;
      }
    }

    // arXiv pattern
    if (url.includes('arxiv.org/abs/')) return url.replace('/abs/', '/pdf/') + '.pdf';

    return null;
  }

  // ── Save PDF ───────────────────────────────────────
  function savePdf(pdfUrl, paperId) {
    return fetch(pdfUrl, { credentials: 'include' })
      .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
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
      .then(function(r) { return r.json(); });
  }

  // ── Floating Save PDF button ───────────────────────
  function injectSaveButton() {
    var B = document.createElement('div');
    B.id = 'litmanger-save-btn';
    B.textContent = 'Save PDF';
    B.style.cssText = [
      'position:fixed;bottom:24px;right:24px;z-index:2147483646',
      'background:linear-gradient(135deg,#0f3460,#1a4a7a)',
      'color:white;padding:12px 26px;border-radius:30px',
      'font:600 15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
      'cursor:pointer;box-shadow:0 4px 16px rgba(15,52,96,.35)',
      'transition:transform .15s,box-shadow .15s',
      'user-select:none'
    ].join(';');

    B.onmouseenter = function() { B.style.transform = 'translateY(-2px)'; B.style.boxShadow = '0 6px 20px rgba(15,52,96,.45)'; };
    B.onmouseleave = function() { B.style.transform = ''; B.style.boxShadow = '0 4px 16px rgba(15,52,96,.35)'; };

    B.onclick = function() {
      var pdfUrl = getPdfUrl();
      var paperId = getPaperId();

      if (!pdfUrl) {
        B.textContent = '✗ No PDF found';
        B.style.background = '#f44336';
        setTimeout(reset, 2500);
        return;
      }

      B.textContent = '⏳ Saving…';
      B.style.background = '#ff9800';
      B.style.pointerEvents = 'none';

      savePdf(pdfUrl, paperId || 'paper')
        .then(function(r) {
          B.textContent = '✓ Saved! (' + (r.size / 1024).toFixed(0) + ' KB)';
          B.style.background = '#4caf50';
          if (paperId) fetch(SERVER + '/api/mark-downloaded?id=' + paperId);
        })
        .catch(function(e) {
          console.error('Litmanger:', e);
          B.textContent = '✗ Error — server running?';
          B.style.background = '#f44336';
        })
        .then(function() { setTimeout(reset, 3000); });
    };

    function reset() {
      B.textContent = 'Save PDF';
      B.style.background = '';
      B.style.pointerEvents = '';
    }

    document.body.appendChild(B);
  }

  // ── Floating + Library button ──────────────────────
  function injectAddButton() {
    if (!getDoi()) return;

    var B = document.createElement('div');
    B.id = 'litmanger-add-btn';
    B.textContent = '+ Library';
    B.style.cssText = [
      'position:fixed;bottom:24px;right:180px;z-index:2147483646',
      'background:white;color:#0f3460;border:2px solid #0f3460',
      'padding:10px 22px;border-radius:30px',
      'font:600 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
      'cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.1)',
      'transition:all .15s',
      'user-select:none'
    ].join(';');

    B.onclick = function() {
      navigator.clipboard.writeText(location.href).then(function() {
        B.textContent = '✓ Copied!';
        B.style.background = '#e8f5e9';
        B.style.borderColor = '#4caf50';
        B.style.color = '#2e7d32';
        setTimeout(function() {
          B.textContent = '+ Library';
          B.style.background = 'white';
          B.style.borderColor = '#0f3460';
          B.style.color = '#0f3460';
        }, 2000);
      });
    };

    document.body.appendChild(B);
  }

  // ── Init ───────────────────────────────────────────
  checkServer().then(function(ok) {
    serverOnline = ok;
    if (ok) {
      injectSaveButton();
      injectAddButton();
      console.log('Litmanger: buttons injected (server found)');
    } else {
      console.log('Litmanger: server not running at ' + SERVER);
    }
  });

})();
