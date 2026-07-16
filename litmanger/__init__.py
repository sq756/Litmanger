"""Litmanger — Academic Paper Manager.

A local-first tool for collecting metadata, BibTeX, and PDFs from
academic journal websites.  Supports APS, arXiv, Nature, and generic
citation_* meta tags out of the box.

Quick start:
    python -m litmanger <url>          Add a paper + download PDF
    python -m litmanger server         Start the dashboard
    python -m litmanger --list         List all papers

Package modules:
    cli         Command-line interface
    models      Paper and PaperDB dataclasses
    fetcher     URL → Paper metadata extraction (multi-publisher)
    pdf         PDF download with browser-cookie support
    templates   HTML dashboard generation
    server      Local HTTP dashboard server
    utils       HTTP helpers, DOI parsing, meta-tag extraction
"""

__version__ = "2.0.0"
