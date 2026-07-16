# Litmanger · 轻量学术论文管理器

[English](#english) | [中文](#%E4%B8%AD%E6%96%87)

---

<a id="english"></a>
## English

Flat-tag, AI-powered academic paper management. **One JSON file, one folder of PDFs.** No accounts, no folders, no database engine.

### Why Litmanger?

Traditional reference managers (Zotero, Mendeley, EndNote) force you into folder hierarchies. But a paper on "quantum error correction with machine learning" belongs in three places at once. Litmanger replaces folders with **flat tags** and replaces manual search with **AI chat** — ask questions about any paper in your library in plain English.

### Quick Start

**Zero-install (Python stdlib only):**

```bash
cd Litmanger
python -m litmanger server                    # Dashboard → http://127.0.0.1:8765
python -m litmanger list                      # List all papers
python -m litmanger https://doi.org/10.1103/PhysRevB.113.235157  # Add a paper
```

No `pip install` needed — core functionality uses only the Python standard library.

**Optional: global install (run from any directory):**

```bash
pip install -e .
litmanger server
litmanger list
litmanger <url>
```

**Optional: enhanced PDF download (institutional access via browser cookies):**

```bash
pip install requests browser-cookie3
```

After installing, `litmanger <url>` automatically reads your Chrome/Edge/Firefox login cookies to download PDFs behind paywalls.

**Windows quick launch:**

```cmd
run                        # Interactive menu
run server                 # Start dashboard
run <url>                  # Add paper
```

### Features

| Feature | Description |
|---------|-------------|
| **Flat tags** | Every paper has tags — no folder hierarchy. Cross-category by design. |
| **AI chat** | Bring your own API key (DeepSeek, OpenAI, or any compatible provider). Discuss papers in natural language. |
| **Multi-publisher** | APS, arXiv, Nature, plus generic `citation_*` meta-tag fallback. Extensible via `@register()`. |
| **Auto BibTeX** | Crossref API with publisher-specific fallback (APS, etc.). |
| **PDF download** | Three strategies: browser cookies → server proxy → manual save. |
| **PDF auto-rename** | Downloaded PDFs renamed to `Author_Year_Title.pdf`. |
| **Tag management** | Add/remove tags inline. |
| **Paper notes** | Per-paper editable notes, included in AI context. |
| **Batch import** | Paste multiple DOIs at once. |
| **Dark mode** | Toggle with persistence (localStorage). |
| **Resizable panels** | Drag to resize left/right panels. |
| **Export** | Single paper JSON, full library BibTeX, or full library JSON. |
| **Browser integration** | Bookmarklet + Tampermonkey userscript for one-click PDF save from journal pages. |
| **PDF auto-archiver** | PowerShell script watches Downloads folder, copies new PDFs to `pdfs/`. |
| **Static HTML** | Export your entire library to a portable `paper_library.html`. |
| **Keyboard shortcuts** | `/` to focus search. |
| **Portable** | Copy `papers.json` + `pdfs/` to migrate. Merge two libraries with JSON dedup. |

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

| Command | Description |
|---------|-------------|
| `litmanger <url>` | Add paper from URL + attempt PDF download |
| `litmanger add <url>` | Add paper (with `--no-download` flag to skip PDF) |
| `litmanger list` | List all papers with metadata |
| `litmanger download <id>` | Re-download PDF for a paper |
| `litmanger open <id>` | Open paper in browser |
| `litmanger mark-done <id>` | Mark PDF as downloaded |
| `litmanger html` | Generate static HTML dashboard (`paper_library.html`) |
| `litmanger server` | Start local dashboard at `http://127.0.0.1:8765` |
| `litmanger server --port 9000` | Start on custom port |

### Browser Integration

**Bookmarklet:** Visit `http://127.0.0.1:8765/install`, drag the **Save PDF** button to your bookmarks bar. Click it on any journal page to save the PDF directly to your library.

**Tampermonkey Userscript:** Install [Tampermonkey](https://www.tampermonkey.net/), then open `http://127.0.0.1:8765/save-paper.user.js`. Floating buttons appear automatically on APS, arXiv, Nature, and other journal sites.

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

**零安装（纯 Python 标准库）：**

```bash
cd Litmanger
python -m litmanger server                     # 启动仪表板 → http://127.0.0.1:8765
python -m litmanger list                       # 列出所有论文
python -m litmanger https://doi.org/10.1103/PhysRevB.113.235157  # 添加论文
```

不需要 `pip install` —— 核心功能只用 Python 标准库。

**可选：全局安装（在任意目录下运行）：**

```bash
pip install -e .
litmanger server
litmanger list
litmanger <url>
```

**可选：增强 PDF 下载（通过浏览器 cookie 过机构认证）：**

```bash
pip install requests browser-cookie3
```

安装后，`litmanger <url>` 会读取你 Chrome/Edge/Firefox 的登录 cookie，自动下载付费墙后的 PDF。

**Windows 快捷启动：**

```cmd
run                        # 交互式菜单
run server                 # 启动仪表板
run <url>                  # 添加论文
```

### 功能

| 功能 | 说明 |
|------|------|
| **扁平标签** | 每篇论文打标签，不建文件夹。天然支持跨分类。 |
| **AI 对话** | 自带 API key（支持 DeepSeek、OpenAI 等兼容接口）。用自然语言讨论论文。 |
| **多出版商** | 支持 APS、arXiv、Nature，以及通用 `citation_*` 元标签。可通过 `@register()` 扩展。 |
| **自动 BibTeX** | Crossref API 获取，含 APS 等特定出版商回退。 |
| **PDF 下载** | 三阶段回退：浏览器 cookie → 服务端代理 → 手动保存。 |
| **PDF 自动重命名** | 下载后自动重命名为 `作者_年份_标题.pdf`。 |
| **标签管理** | 行内增删标签。 |
| **论文笔记** | 每篇论文可编辑笔记，AI 对话时自动注入上下文。 |
| **批量导入** | 一次粘贴多个 DOI。 |
| **深色模式** | 一键切换，自动记忆（localStorage）。 |
| **可拖拽面板** | 左右面板拖拽调整宽度。 |
| **导出** | 单篇 JSON、全文库 BibTeX、全文库 JSON。 |
| **浏览器集成** | Bookmarklet + Tampermonkey 脚本，期刊页面一键保存 PDF。 |
| **PDF 自动归档** | PowerShell 脚本监控 Downloads 文件夹，自动复制新 PDF 到 `pdfs/`。 |
| **静态 HTML** | 导出整个论文库为便携 `paper_library.html`。 |
| **键盘快捷键** | `/` 聚焦搜索框。 |
| **极致便携** | 拷贝 `papers.json` + `pdfs/` 即迁移。两个库合并只需 JSON 去重。 |

### 项目结构

```
Litmanger/
├── litmanger/              # Python 包
│   ├── __init__.py         # 包元数据 (v2.0.0)
│   ├── __main__.py         # python -m litmanger 入口
│   ├── cli.py              # CLI：add, list, server, download, open, html
│   ├── models.py           # Paper & PaperDB 数据类
│   ├── fetcher.py          # 多出版商元数据提取
│   ├── pdf.py              # PDF 下载器（浏览器 cookie）
│   ├── server.py           # 本地 HTTP 仪表板（仅 127.0.0.1）
│   ├── templates.py        # HTML 仪表板生成
│   └── utils.py            # DOI 解析、HTTP、路径安全
├── static/                 # 浏览器集成
│   ├── bookmarklet.js      # 拖到书签栏的"保存 PDF"按钮
│   └── save-paper.user.js  # Tampermonkey 脚本（自动注入按钮）
├── server.py               # 独立服务器（v1 回退，无需包依赖）
├── index.html              # 独立 SPA（v1 回退）
├── papers.json             # 论文数据库（可读、可 git diff）
├── config.json             # API 配置
├── pdfs/                   # 已下载 PDF
├── pyproject.toml          # 包构建配置
├── requirements.txt        # 可选依赖
├── run.bat / run.sh        # 快捷启动脚本
└── watch_downloads.ps1     # PDF 自动归档
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `litmanger <url>` | 从 URL 添加论文 + 自动下载 PDF |
| `litmanger add <url>` | 添加论文（加 `--no-download` 跳过 PDF） |
| `litmanger list` | 列出所有论文及元数据 |
| `litmanger download <id>` | 重新下载某篇论文的 PDF |
| `litmanger open <id>` | 在浏览器中打开论文 |
| `litmanger mark-done <id>` | 标记 PDF 已下载 |
| `litmanger html` | 生成静态 HTML 仪表板 (`paper_library.html`) |
| `litmanger server` | 启动本地仪表板 `http://127.0.0.1:8765` |
| `litmanger server --port 9000` | 自定义端口 |

### 浏览器集成

**Bookmarklet：** 访问 `http://127.0.0.1:8765/install`，把 **Save PDF** 按钮拖到书签栏。在期刊页面点击即可保存 PDF。

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
