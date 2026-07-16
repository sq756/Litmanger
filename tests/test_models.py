"""Tests for litmanger.models — Paper, PaperDB."""

import json

from litmanger.models import Paper, PaperDB


class TestPaper:
    def test_from_dict_basic(self, sample_paper_dict):
        p = Paper.from_dict(sample_paper_dict)
        assert p.id == "PhysRevB.113.235157"
        assert p.title == "Learning variational quantum circuit parameters"
        assert p.year == "2025"

    def test_from_dict_defaults(self):
        p = Paper.from_dict({"id": "test-1", "title": "Minimal Paper"})
        assert p.authors == []
        assert p.tags == []
        assert p.pdf_downloaded is False

    def test_from_dict_ignores_extra_keys(self):
        p = Paper.from_dict({"id": "x", "title": "X", "unknown_field": 999})
        assert p.id == "x"

    def test_to_dict_roundtrip(self, sample_paper_dict):
        p = Paper.from_dict(sample_paper_dict)
        output = p.to_dict()
        assert output["id"] == sample_paper_dict["id"]
        assert output["title"] == sample_paper_dict["title"]
        assert output["authors"] == sample_paper_dict["authors"]

    def test_author_line_single(self):
        p = Paper(id="a", title="T", authors=["Alice"])
        assert p.author_line == "Alice"

    def test_author_line_multiple(self):
        p = Paper(id="a", title="T", authors=["Alice", "Bob", "Charlie"])
        assert p.author_line == "Alice, Bob, Charlie"

    def test_author_line_et_al(self):
        p = Paper(id="a", title="T", authors=["Alice", "Bob", "Charlie", "Dave"])
        assert p.author_line == "Alice et al."

    def test_author_line_unknown(self):
        p = Paper(id="a", title="T")
        assert p.author_line == "Unknown"


class TestPaperDB:
    def test_load_from_file(self, papers_json):
        db = PaperDB.load(papers_json)
        assert db.count == 1
        assert db.papers[0].id == "PhysRevB.113.235157"

    def test_load_new_file(self, empty_papers_json):
        db = PaperDB.load(empty_papers_json)
        assert db.count == 0

    def test_load_missing_file(self, tmp_path):
        db = PaperDB.load(tmp_path / "nonexistent.json")
        assert db.count == 0

    def test_save_and_reload(self, tmp_path, sample_paper_dict):
        path = tmp_path / "out.json"
        p = Paper.from_dict(sample_paper_dict)
        db = PaperDB(papers=[p], _path=path)
        db.save()
        reloaded = PaperDB.load(path)
        assert reloaded.count == 1
        assert reloaded.papers[0].id == p.id

    def test_add_new(self):
        db = PaperDB()
        p = Paper(id="new-1", title="New Paper", doi="10.1234/test")
        assert db.add(p) is True
        assert db.count == 1

    def test_add_duplicate_doi(self, sample_paper_dict):
        p1 = Paper.from_dict(sample_paper_dict)
        p2 = Paper(id="updated-id", title="Updated Title", doi=p1.doi)
        db = PaperDB(papers=[p1])
        assert db.add(p2) is False
        assert db.count == 1
        assert db.papers[0].title == "Updated Title"

    def test_find_by_doi(self):
        p = Paper(id="x", title="T", doi="10.1234/test")
        db = PaperDB(papers=[p])
        assert db.find_by_doi("10.1234/test") is p
        assert db.find_by_doi("10.9999/nope") is None

    def test_find_by_id(self):
        p = Paper(id="my-id", title="T", doi="10.1234/test")
        db = PaperDB(papers=[p])
        assert db.find_by_id("my-id") is p
        assert db.find_by_id("other") is None

    def test_mark_pdf(self):
        p = Paper(id="x", title="T")
        db = PaperDB(papers=[p])
        assert db.mark_pdf("x", "/tmp/test.pdf") is True
        assert db.papers[0].pdf_downloaded is True
        assert db.papers[0].pdf_local == "/tmp/test.pdf"

    def test_mark_pdf_not_found(self):
        db = PaperDB()
        assert db.mark_pdf("ghost") is False

    def test_remove(self):
        p = Paper(id="x", title="T")
        db = PaperDB(papers=[p])
        assert db.remove("x") is True
        assert db.count == 0

    def test_remove_not_found(self):
        assert PaperDB().remove("x") is False

    def test_search(self):
        papers = [
            Paper(id="1", title="Quantum Computing", authors=["Alice"]),
            Paper(id="2", title="Classical Physics", authors=["Bob"]),
        ]
        db = PaperDB(papers=papers)
        assert len(db.search("quantum")) == 1
        assert len(db.search("physics")) == 2
        assert len(db.search("xyz")) == 0

    def test_pdf_count(self):
        p1 = Paper(id="1", title="A", pdf_downloaded=True)
        p2 = Paper(id="2", title="B", pdf_downloaded=False)
        db = PaperDB(papers=[p1, p2])
        assert db.pdf_count == 1

    def test_year_range(self):
        p1 = Paper(id="1", title="A", year="2020")
        p2 = Paper(id="2", title="B", year="2024")
        db = PaperDB(papers=[p1, p2])
        assert db.year_range == (2020, 2024)

    def test_year_range_empty(self):
        assert PaperDB().year_range is None
