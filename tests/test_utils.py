"""Tests for litmanger.utils — DOI, path safety, meta extraction."""

from pathlib import Path

from litmanger.utils import (
    extract_doi,
    extract_meta_name,
    extract_meta_names,
    paper_id_from_doi,
    safe_path_under,
)


class TestExtractDoi:
    def test_aps_url(self):
        assert extract_doi(
            "https://journals.aps.org/prb/abstract/10.1103/PhysRevB.113.235157"
        ) == "10.1103/PhysRevB.113.235157"

    def test_doi_org_url(self):
        assert extract_doi("https://doi.org/10.1038/s41586-023-12345") == "10.1038/s41586-023-12345"

    def test_bare_doi(self):
        assert extract_doi("10.1002/adma.202301234") == "10.1002/adma.202301234"

    def test_no_doi_returns_none(self):
        assert extract_doi("https://example.com/not-a-doi") is None

    def test_empty_string(self):
        assert extract_doi("") is None


class TestPaperIdFromDoi:
    def test_standard_doi(self):
        assert paper_id_from_doi("10.1103/PhysRevB.113.235157") == "PhysRevB.113.235157"

    def test_nature_doi(self):
        assert paper_id_from_doi("10.1038/s41586-023-12345") == "s41586-023-12345"


class TestExtractMetaName:
    def test_double_quoted(self):
        html = '<meta name="citation_title" content="A Great Paper">'
        assert extract_meta_name(html, "citation_title") == "A Great Paper"

    def test_single_quoted(self):
        html = "<meta name='citation_title' content='Another Paper'>"
        assert extract_meta_name(html, "citation_title") == "Another Paper"

    def test_case_insensitive(self):
        html = '<META NAME="citation_title" CONTENT="Case Test">'
        assert extract_meta_name(html, "citation_title") == "Case Test"

    def test_not_found(self):
        assert extract_meta_name("<html></html>", "citation_title") is None


class TestExtractMetaNames:
    def test_multiple_authors(self):
        html = (
            '<meta name="citation_author" content="Alice">'
            '<meta name="citation_author" content="Bob">'
        )
        assert extract_meta_names(html, "citation_author") == ["Alice", "Bob"]

    def test_single_author(self):
        html = '<meta name="citation_author" content="Solo">'
        assert extract_meta_names(html, "citation_author") == ["Solo"]

    def test_no_authors(self):
        assert extract_meta_names("<html></html>", "citation_author") == []


class TestSafePathUnder:
    def test_valid_relative(self, tmp_path):
        (tmp_path / "sub").mkdir()
        result = safe_path_under(tmp_path, "sub")
        assert result == (tmp_path / "sub").resolve()

    def test_traversal_blocked(self, tmp_path):
        result = safe_path_under(tmp_path, "../../etc/passwd")
        assert result is None

    def test_absolute_within_base(self, tmp_path):
        (tmp_path / "data").mkdir()
        result = safe_path_under(tmp_path, str(tmp_path / "data"))
        assert result is not None

    def test_absolute_outside_base(self, tmp_path):
        result = safe_path_under(tmp_path, "/etc")
        assert result is None
