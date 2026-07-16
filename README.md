# Litmanger · 轻量学术论文管理器

[English](#english) | [中文](#%E4%B8%AD%E6%96%87)

---

<a id="english"></a>
## English

Flat-tag, AI-powered academic paper management. **One JSON file, one folder of PDFs.** No accounts, no folders, no database engine.

### Why Litmanger?

Traditional reference managers (Zotero, Mendeley, EndNote) force you into folder hierarchies. But a paper on "quantum error correction with machine learning" belongs in three places at once. Litmanger replaces folders with **flat tags** and replaces manual search with **AI chat** — ask questions about any paper in your library in plain English.

### Quick Start

**Double-click `run.bat` (Windows)** or run:

```bash
python server.py                                # Dashboard → http://127.0.0.1:8766
```

No `pip install` needed — uses only the Python standard library.

**Alternative: litmanger package (full CLI):**

```bash
pip install -e .
litmanger server                                # Dashboard → http://127.0.0.1:8765
litmanger list                                  # List all papers
litmanger https://doi.org/10.1103/PhysRevB.113.235157  # Add a paper
```

The standalone `server.py` (port 8766) is the main UI with all features: three-panel layout, AI chat, PDF preview, sort, themes, Markdown notes, and comments. The litmanger package (port 8765) adds CLI tools, bookmarklet support, and PDF download with browser cookies.

### Features

| Feature | Description |
|---------|-------------|
| **Flat tags** | Every paper has tags — no folder hierarchy. Cross-category by design. |
| **AI chat** | Bring your own API key (DeepSeek, OpenAI, or any compatible provider). |
| **Auto metadata** | Paste a DOI, arXiv, or journal URL — auto-extracts title, authors, journal, year, abstract, BibTeX. |
| **PDF preview** | Split-view PDF reader in the center panel. |
| **PDF download** | Open Online → save to Downloads or pdfs/ → Mark Done → preview works. |
| **PDF auto-scan** | Auto-Scan PDFs finds downloaded PDFs in Downloads/ and pdfs/, matches by paper ID. |
| **P2P comments** | DOI-based comments with Ed25519 signing + optional relay server for sharing. |
| **Markdown notes** | Per-paper Markdown editor with live preview and KaTeX math ($\LaTeX$). |
| **Tag management** | Add/remove tags inline. |
| **Sort & filter** | 8 sort modes (date, year, title, author, journal) + keyword filter. |
| **Theme system** | 6 color presets, custom accent, background images/videos, opacity, blur. |
| **Dark mode** | Toggle with persistence. |
| **Resizable panels** | Drag handles between all three panels. |
| **Batch import** | Paste multiple DOIs at once. |
| **Export** | Single paper JSON, full library BibTeX, full library JSON, static HTML. |
| **Browser integration** | Bookmarklet + Tampermonkey (requires litmanger package, port 8765). |
| **Keyboard shortcuts** | `/` to focus filter. |
| **Portable** | Copy `papers.json` + `pdfs/` to migrate. Standalone `.exe` available. |

### Architecture

```
Litmanger/
├── litmanger/              # Python package
│   ├── __init__.py         # Package metadata (v2.0.0)
│   ├── __main__.py         # python -m litmanger entry point
│   ├── cli.py              # CLI: add, list, server, download, open, html
│   ├── models.py           # Paper & PaperDB dataclasses
│   ├── fetcher.py          # Multi-publisher metadata extraction
│   ├── pdf.py              # PDF downloader with browser-cookie support
│   ├── server.py           # Local HTTP dashboard (127.0.0.1 only)
│   ├── templates.py        # HTML dashboard generation
│   └── utils.py            # DOI parsing, HTTP, path safety
├── static/                 # Browser integration
│   ├── bookmarklet.js      # Drag-to-bookmarks-bar "Save PDF" button
│   └── save-paper.user.js  # Tampermonkey userscript (auto-injects buttons)
├── server.py               # Standalone server (v1 fallback, no package deps)
├── index.html              # Standalone SPA (v1 fallback)
├── papers.json             # Paper database (human-readable, git-diffable)
├── config.json             # API configuration
├── pdfs/                   # Downloaded PDFs
├── pyproject.toml          # Package build config
├── requirements.txt        # Optional dependencies
├── run.bat / run.sh        # Convenience launchers
└── watch_downloads.ps1     # PDF auto-archiver
```

### CLI Reference

**Standalone server** (`python server.py`, port 8766) — the main UI:

| Command | Description |
|---------|-------------|
| `python server.py` | Start dashboard at `http://127.0.0.1:8766` (auto-opens browser) |

All features work through the web UI: add papers, sort, filter, download PDFs, AI chat, Markdown notes, comments, themes, export.

**litmanger package CLI** (requires `pip install -e .`, port 8765):

| Command | Description |
|---------|-------------|
| `litmanger <url>` | Add paper from URL + attempt PDF download |
| `litmanger add <url>` | Add paper (with `--no-download` to skip PDF) |
| `litmanger list` | List all papers |
| `litmanger download <id>` | Re-download PDF |
| `litmanger open <id>` | Open paper in browser |
| `litmanger mark-done <id>` | Mark PDF as downloaded |
| `litmanger html` | Generate static `paper_library.html` |
| `litmanger server` | Dashboard at `http://127.0.0.1:8765` |

### Browser Integration

> **Requires the litmanger package** (`pip install -e .` + `litmanger server` on port 8765).  
> The standalone `python server.py` (port 8766) does not have bookmarklet routes.

**Bookmarklet:** Visit `http://127.0.0.1:8765/install`, drag the **Save PDF** button to your bookmarks bar. Click on any journal page to save the PDF directly to `pdfs/`.

**Tampermonkey Userscript:** Install [Tampermonkey](https://www.tampermonkey.net/), then open `http://127.0.0.1:8765/save-paper.user.js`. Floating buttons appear on APS, arXiv, Nature, and other journal sites.

### Paper Data Schema

```json
{
  "id": "arxiv-id-or-doi-suffix",
  "title": "Paper Title",
  "authors": ["Author One", "Author Two"],
  "journal": "Journal Name",
  "year": "2024",
  "doi": "10.xxxx/xxxxx",
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
```

### Security

- Server binds to **127.0.0.1 only** — never exposed to the network.
- PDF serving uses **path sanitization** — path traversal blocked.
- CORS restricted to local origins only.

### Requirements

- Python 3.9+
- Optional: `requests`, `browser-cookie3` (for enhanced PDF download with institutional access)
- Optional: `beautifulsoup4`, `bibtexparser` (for richer metadata and export)

### License

MIT

---

<a id="中文"></a>
## 中文

扁平标签 + AI 驱动的轻量学术论文管理器。**一个 JSON 文件，一个 PDF 文件夹。** 无需账号，无需文件夹层级，无需数据库。

### 为什么用 Litmanger？

传统的文献管理软件（Zotero、Mendeley、EndNote）让你建文件夹树。但一篇"量子误差修正 + 机器学习"的论文该放哪个文件夹？Litmanger 用**扁平标签**替代层级，用 **AI 对话**替代手动检索——用自然语言问你的论文库任何问题。

### 快速开始

**双击 `run.bat`（Windows）** 或运行：

```bash
python server.py                                # 仪表板 → http://127.0.0.1:8766
```

不需要 `pip install` —— 只用 Python 标准库。

**可选：litmanger 包（完整 CLI）：**

```bash
pip install -e .
litmanger server                                # 仪表板 → http://127.0.0.1:8765
litmanger list                                  # 列出所有论文
litmanger https://doi.org/10.1103/PhysRevB.113.235157  # 添加论文
```

独立版 `server.py`（端口 8766）是主入口，包含所有功能：三栏布局、AI 对话、PDF 预览、排序、主题、Markdown 笔记和评论。litmanger 包（端口 8765）额外提供 CLI 工具、bookmarklet 支持和浏览器 cookie PDF 下载。

**Windows 快捷启动：**

```cmd
双击 run.bat                # 自动检测 Python，启动 server.py → 浏览器打开
```

### 功能

| 功能 | 说明 |
|------|------|
| **扁平标签** | 每篇论文打标签，不建文件夹。天然支持跨分类。 |
| **AI 对话** | 自带 API key（支持 DeepSeek、OpenAI 等兼容接口）。 |
| **自动元数据** | 粘贴 DOI、arXiv 或期刊链接，自动提取标题、作者、期刊、年份、摘要、BibTeX。 |
| **PDF 预览** | 中间栏分屏 PDF 阅读器。 |
| **PDF 下载** | Open Online → 保存到 Downloads 或 pdfs/ → Mark Done → 预览即可用。 |
| **PDF 自动扫描** | Auto-Scan PDFs 自动匹配 Downloads/ 和 pdfs/ 中的 PDF，按论文 ID 关联。 |
| **P2P 评论** | 基于 DOI 的评论系统，Ed25519 签名 + 可选中继服务器共享。 |
| **Markdown 笔记** | 每篇论文的 Markdown 编辑器，带实时预览和 KaTeX 数学公式渲染。 |
| **标签管理** | 行内增删标签。 |
| **排序与过滤** | 8 种排序模式（日期、年份、标题、作者、期刊）+ 关键字过滤。 |
| **主题系统** | 6 套预设配色、自定义强调色、背景图片/视频、透明度、模糊。 |
| **深色模式** | 一键切换，自动记忆。 |
| **可拖拽面板** | 三个面板之间可拖拽调整宽度。 |
| **批量导入** | 一次粘贴多个 DOI。 |
| **导出** | 单篇 JSON、全文库 BibTeX、全文库 JSON、静态 HTML。 |
| **浏览器集成** | Bookmarklet + Tampermonkey（需要 litmanger 包，端口 8765）。 |
| **键盘快捷键** | `/` 聚焦过滤框。 |
| **极致便携** | 拷贝 `papers.json` + `pdfs/` 即迁移。提供独立 `.exe` 免 Python 运行。 |

### 项目结构

```
Litmanger/
├── server.py               # 独立服务器（端口 8766，零依赖主入口）
├── index.html              # 单文件 SPA（三栏布局，全部功能）
├── relay_server.py         # Ed25519 签名评论中继服务器（端口 9987）
├── build_exe.py            # PyInstaller 构建脚本 → dist/Litmanger.exe
├── litmanger/              # Python 包（v2.0.0，备选入口）
│   ├── cli.py              # 完整 CLI：add, list, server, download, open, html
│   ├── models.py           # Paper & PaperDB 数据类
│   ├── fetcher.py          # 多出版商元数据提取（APS, arXiv, Nature）
│   ├── pdf.py              # PDF 下载器（浏览器 cookie）
│   ├── server.py           # 包 HTTP 仪表板（端口 8765）
│   ├── templates.py        # HTML 仪表板生成
│   └── utils.py            # DOI 解析、HTTP 帮助函数
├── static/                 # 浏览器集成（仅 litmanger 包）
│   ├── bookmarklet.js      # "保存 PDF"书签
│   └── save-paper.user.js  # Tampermonkey 脚本
├── papers.json             # 论文数据库（可读、可 git diff）
├── config.json             # API 配置
├── pdfs/                   # 已下载 PDF
├── pyproject.toml          # 包构建配置
├── run.bat / run.sh        # 启动脚本
└── watch_downloads.ps1     # PDF 自动归档
```
├── config.json             # API 配置
├── pdfs/                   # 已下载 PDF
├── pyproject.toml          # 包构建配置
├── requirements.txt        # 可选依赖
├── run.bat / run.sh        # 快捷启动脚本
└── watch_downloads.ps1     # PDF 自动归档
```

### CLI 命令

**独立版服务器**（`python server.py`，端口 8766）—— 主界面：

| 命令 | 说明 |
|------|------|
| `python server.py` | 启动仪表板 `http://127.0.0.1:8766`（自动打开浏览器） |

所有功能通过 Web 界面操作：添加论文、排序、过滤、下载 PDF、AI 对话、Markdown 笔记、评论、主题、导出。

**litmanger 包 CLI**（需先 `pip install -e .`，端口 8765）：

| 命令 | 说明 |
|------|------|
| `litmanger <url>` | 从 URL 添加论文 |
| `litmanger add <url>` | 添加论文（加 `--no-download` 跳过 PDF） |
| `litmanger list` | 列出所有论文 |
| `litmanger download <id>` | 重新下载 PDF |
| `litmanger open <id>` | 在浏览器中打开论文 |
| `litmanger mark-done <id>` | 标记 PDF 已下载 |
| `litmanger html` | 生成静态 `paper_library.html` |
| `litmanger server` | 仪表板 `http://127.0.0.1:8765` |

### 浏览器集成

> **需要 litmanger 包**（`pip install -e .` + `litmanger server` 启动到端口 8765）。  
> 独立版 `python server.py`（端口 8766）不含 bookmarklet 路由。

**Bookmarklet：** 访问 `http://127.0.0.1:8765/install`，把 **Save PDF** 按钮拖到书签栏。在期刊页面点击即可保存 PDF 到 `pdfs/`。

**Tampermonkey 脚本：** 安装 [Tampermonkey](https://www.tampermonkey.net/) 后，打开 `http://127.0.0.1:8765/save-paper.user.js`。在 APS、arXiv、Nature 等期刊页面自动显示浮动保存按钮。

### 论文数据格式

```json
{
  "id": "arxiv-id-or-doi-suffix",
  "title": "论文标题",
  "authors": ["作者一", "作者二"],
  "journal": "期刊名",
  "year": "2024",
  "doi": "10.xxxx/xxxxx",
  "url": "https://...",
  "pdf_url": "https://...",
  "abstract": "摘要...",
  "bibtex": "@article{...}",
  "tags": ["标签1", "标签2"],
  "notes": "我的笔记",
  "pdf_downloaded": true,
  "pdf_local": "pdfs/Author_2024_Title.pdf",
  "added": "2024-01-15"
}
```

### 安全性

- 服务器仅绑定 **127.0.0.1** —— 绝不暴露到网络。
- PDF 文件服务使用**路径消毒** —— 阻止目录穿越攻击。
- CORS 仅允许本地来源。

### 环境要求

- Python 3.9+
- 可选：`requests`、`browser-cookie3`（用于机构认证 PDF 下载）
- 可选：`beautifulsoup4`、`bibtexparser`（用于更丰富的元数据和导出）

### 许可证

MIT
