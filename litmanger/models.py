"""Data models for Litmanger."""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class Paper:
    """A single academic paper."""

    id: str
    title: str
    authors: list[str] = dataclasses.field(default_factory=list)
    journal: str = ""
    doi: str = ""
    url: str = ""
    pdf_url: str = ""
    bibtex: str | None = None
    abstract: str = ""
    year: str = ""
    month: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    added: str = dataclasses.field(default_factory=lambda: str(date.today()))
    tags: list[str] = dataclasses.field(default_factory=list)
    pdf_downloaded: bool = False
    pdf_local: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Paper:
        """Build a Paper from a dictionary (with defaults for missing keys)."""
        # Filter to known fields so legacy JSON with extra keys doesn't break
        field_names = {f.name for f in dataclasses.fields(cls)}
        clean = {k: v for k, v in d.items() if k in field_names}
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def author_line(self) -> str:
        """First-author et al. style citation string."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def citation(self) -> str:
        """Short inline citation: Author (Year), Journal Volume, Pages."""
        parts = [self.author_line]
        if self.year:
            parts.append(f"({self.year})")
        if self.journal:
            parts.append(self.journal)
        if self.volume:
            vol = f"Vol. {self.volume}"
            if self.pages:
                vol += f", {self.pages}"
            parts.append(vol)
        return ", ".join(parts)


@dataclasses.dataclass
class PaperDB:
    """In-memory paper database with JSON persistence."""

    papers: list[Paper] = dataclasses.field(default_factory=list)
    _path: Path | None = dataclasses.field(default=None, repr=False)

    # ── I/O ──────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> PaperDB:
        """Load database from a JSON file."""
        if path.exists():
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("papers", raw if isinstance(raw, list) else [])
            papers = [Paper.from_dict(p) for p in items]
            db = cls(papers=papers, _path=path)
        else:
            db = cls(_path=path)
        return db

    def save(self, path: Path | None = None) -> None:
        """Persist database to JSON."""
        target = path or self._path
        if target is None:
            raise ValueError("No save path configured")
        data = {"papers": [p.to_dict() for p in self.papers]}
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── queries ──────────────────────────────────────────

    def find_by_doi(self, doi: str) -> Paper | None:
        for p in self.papers:
            if p.doi == doi:
                return p
        return None

    def find_by_id(self, paper_id: str) -> Paper | None:
        for p in self.papers:
            if p.id == paper_id:
                return p
        return None

    # ── mutations ────────────────────────────────────────

    def add(self, paper: Paper) -> bool:
        """Add a paper, or update if DOI already exists. Returns True if new."""
        existing = self.find_by_doi(paper.doi)
        if existing:
            # Update in place
            for f in dataclasses.fields(Paper):
                new_val = getattr(paper, f.name)
                if new_val:  # don't overwrite with empty defaults
                    setattr(existing, f.name, new_val)
            return False
        self.papers.insert(0, paper)
        return True

    def upsert(self, paper: Paper) -> None:
        """Insert or replace by DOI."""
        for i, p in enumerate(self.papers):
            if p.doi == paper.doi:
                self.papers[i] = paper
                return
        self.papers.insert(0, paper)

    def mark_pdf(self, paper_id: str, local_path: str | None = None) -> bool:
        """Mark a paper's PDF as downloaded. Returns False if not found."""
        paper = self.find_by_id(paper_id)
        if paper is None:
            return False
        paper.pdf_downloaded = True
        if local_path:
            paper.pdf_local = local_path
        return True

    def remove(self, paper_id: str) -> bool:
        """Remove a paper by ID. Returns False if not found."""
        for i, p in enumerate(self.papers):
            if p.id == paper_id:
                self.papers.pop(i)
                return True
        return False

    # ── properties ───────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self.papers)

    @property
    def pdf_count(self) -> int:
        return sum(1 for p in self.papers if p.pdf_downloaded)

    @property
    def year_range(self) -> tuple[int, int] | None:
        years = [int(p.year) for p in self.papers if p.year and p.year.isdigit()]
        if not years:
            return None
        return (min(years), max(years))

    def search(self, query: str) -> list[Paper]:
        """Case-insensitive search across title, authors, journal, tags, abstract, DOI."""
        q = query.lower()
        results = []
        for p in self.papers:
            haystack = " ".join([
                p.title, p.journal,
                " ".join(p.authors), " ".join(p.tags),
                p.doi, p.abstract or "",
            ]).lower()
            if q in haystack:
                results.append(p)
        return results
