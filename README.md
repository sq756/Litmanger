# LitManager

Flat-tag, AI-powered literature management. One JSON file, one folder of PDFs. No accounts, no hierarchy, no database engine.

## Quick Start

`ash
# Double-click run.bat, or:
pip install -r requirements.txt  # none needed - stdlib only!
python server.py
# Then open http://127.0.0.1:8766
`

## Features

- **Flat tags, not folders** — Every paper has tags instead of being in a single folder. Cross-category by design.
- **AI chat built-in** — Bring your own DeepSeek API key. Ask questions about any paper in your library.
- **Auto metadata fetch** — Paste a DOI or arXiv link, auto-extract title, authors, journal, abstract, BibTeX.
- **PDF auto-download** — Three-stage fallback: browser cookies > server proxy > manual save.
- **PDF auto-rename** — Downloaded PDFs renamed to Author_Year_Title.pdf.
- **Tag management** — Add/remove tags inline. AI-suggested tags planned.
- **Paper notes** — Per-paper editable notes. Included in AI context when discussing.
- **Batch import** — Paste multiple DOIs at once.
- **Dark mode** — Toggle with persistence.
- **Resizable panels** — Drag to resize left/right panels.
- **Export** — Single paper JSON, full library BibTeX or JSON.
- **Keyboard shortcuts** — / to focus search.
- **Portable** — Copy papers.json + pdfs/ to migrate. Merge two libraries with JSON dedup.

## Architecture

`
litmanager/
├── server.py          # Python backend (stdlib only, no deps)
├── index.html         # Frontend SPA (vanilla HTML/CSS/JS)
├── papers.json        # Paper database (single JSON file)
├── config.json        # API configuration
├── pdfs/              # Downloaded PDFs
├── README.md          # This file
├── run.bat            # Quick start (Windows)
└── .gitignore
`

- **Backend**: Python http.server.ThreadingHTTPServer. No pip install needed.
- **Frontend**: Pure HTML/CSS/JS. No framework, no build step, no Node.js.
- **Data**: papers.json — human-readable, git-diffable, copy-paste portable.
- **AI**: OpenAI-compatible API proxy. Configure DeepSeek (or any compatible provider) in Settings.

## Paper Data Schema

`json
{
  "id": "arxiv-id-or-doi-suffix",
  "title": "Paper Title",
  "authors": ["Author One", "Author Two"],
  "journal": "Journal Name",
  "year": "2024",
  "doi": "10.xxxx/xxxxx",
  "arxiv_id": "2401.00001",
  "url": "https://...",
  "pdf_url": "https://...",
  "abstract": "...",
  "bibtex": "@article{...}",
  "tags": ["tag1", "tag2"],
  "notes": "My notes about this paper",
  "pdf_downloaded": true,
  "pdf_local": "pdfs/Author_2024_Title.pdf",
  "added": "2024-01-15"
}
`

## Campus Network PDF Download

On a campus network with institutional journal access:
1. Click "Download PDF" on a paper
2. Browser fetch uses your institutional cookies
3. PDF saves to pdfs/ and auto-renames

If browser fetch fails (CORS), the server proxies the download as fallback.

## GitHub Release

`ash
git init
git add .
git commit -m "Initial release"
git remote add origin https://github.com/YOU/litmanager.git
git push -u origin main
`

No build step needed — it's all source-ready.

## License

MIT
