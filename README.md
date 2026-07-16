# Litmanger

Academic paper manager — collect metadata, BibTeX, and PDFs from journal URLs.

## Quick Start（新电脑上零安装即用）

```powershell
# 1. 进入项目目录
cd Litmanger

# 2. 直接运行（纯 Python 标准库，不需要 pip install 任何东西）
python -m litmanger --list                         # 列出所有论文
python -m litmanger server                          # 启动仪表板 → http://127.0.0.1:8765
python -m litmanger https://doi.org/10.1103/xxx     # 添加论文
```

> **为什么不需要安装？** Python 会自动搜索当前目录下的 `litmanger/` 包。所有核心功能（元数据抓取、BibTeX、HTML 仪表板、本地服务器）只用标准库，不依赖任何第三方库。

## 可选：全局安装（让 `litmanger` 命令在任何目录都能用）

```powershell
pip install -e .
```

之后就可以从任意目录直接用：

```powershell
litmanger --list
litmanger server
litmanger https://doi.org/10.1103/xxx
```

## 可选：增强 PDF 下载（利用浏览器 cookie 过机构认证）

核心功能已经可以下载开放获取的 PDF。如果你需要**通过机构订阅下载付费墙后的 PDF**，装两个依赖：

```powershell
pip install requests browser-cookie3
```

之后 `litmanger <url>` 会自动读取你 Chrome/Edge/Firefox 的登录 cookie 来下载 PDF。

## 快捷启动脚本（Windows）

```cmd
run server      # 启动仪表板
run list        # 列出论文
run <URL>       # 添加论文
```

## Features

- **Multi-publisher support** — APS journals, arXiv, Nature, plus generic citation-meta fallback
- **Automatic BibTeX** — fetched from Crossref API (with APS fallback)
- **PDF download** — uses browser cookies for institutional access (`browser_cookie3` + `requests`)
- **Local dashboard** — web UI at `http://127.0.0.1:8765` with search, BibTeX copy, and export
- **One-click save** — bookmarklet and Tampermonkey userscript for saving PDFs directly from journal pages
- **Static HTML generation** — export your entire library to a portable HTML file
- **PDF auto-archiver** — PowerShell script watches Downloads folder for new PDFs

## Architecture

```
Litmanger/
├── litmanger/          # Python package
│   ├── cli.py          # CLI (argparse-based)
│   ├── models.py       # Paper & PaperDB dataclasses
│   ├── fetcher.py      # Multi-publisher metadata extraction
│   ├── pdf.py          # PDF downloader (browser cookies)
│   ├── server.py       # Local HTTP dashboard
│   ├── templates.py    # HTML dashboard generation
│   └── utils.py        # DOI parsing, HTTP, path safety
├── static/             # Frontend assets
│   ├── bookmarklet.js  # Bookmarklet source
│   └── save-paper.user.js  # Tampermonkey userscript
├── pdfs/               # Downloaded PDFs
├── papers.json         # Paper database
├── run.bat / run.sh    # Convenience launchers
└── watch_downloads.ps1 # PDF auto-archiver
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `litmanger <url>` | Add paper from URL + attempt PDF download |
| `litmanger --list` | List all papers |
| `litmanger --download <id>` | Re-download PDF for a paper |
| `litmanger --open <id>` | Open paper in browser |
| `litmanger --mark-done <id>` | Mark PDF as downloaded |
| `litmanger --html` | Generate static HTML dashboard |
| `litmanger server` | Start local dashboard (http://127.0.0.1:8765) |
| `litmanger server --port 9000` | Start on custom port |

## Browser Integration

### Bookmarklet
Visit `http://127.0.0.1:8765/install` and drag the "Save PDF" button to your bookmarks bar.
Click it on any journal page to save the PDF directly to your library.

### Tampermonkey Userscript
Install [Tampermonkey](https://www.tampermonkey.net/), then open `http://127.0.0.1:8765/save-paper.user.js`.
Floating buttons appear automatically on APS, arXiv, Nature, and other journal sites.

## Security

- Server binds to **127.0.0.1 only** — never exposed to the network
- PDF serving uses **path sanitization** — path traversal blocked
- CORS restricted to local origins

## Requirements

- Python 3.9+
- Optional: `requests`, `browser-cookie3` (for better PDF download with institutional access)

## License

MIT
