"""Shared test fixtures."""

import json

import pytest


@pytest.fixture
def sample_paper_dict():
    """A valid paper dict matching the schema."""
    return {
        "id": "PhysRevB.113.235157",
        "title": "Learning variational quantum circuit parameters",
        "authors": ["Xin Li", "Zhang-Qi Yin"],
        "journal": "Physical Review B",
        "doi": "10.1103/PhysRevB.113.235157",
        "url": "https://journals.aps.org/prb/abstract/10.1103/PhysRevB.113.235157",
        "year": "2025",
        "volume": "113",
        "pages": "235157",
        "abstract": "We investigate quantum phase transitions using classical AI.",
        "bibtex": "@article{li2025, title={Learning}, journal={PRB}, year={2025}}",
        "tags": ["quantum", "machine-learning"],
        "pdf_downloaded": True,
        "pdf_local": "/tmp/test.pdf",
    }


@pytest.fixture
def papers_json(tmp_path, sample_paper_dict):
    """Create a temporary papers.json with one paper."""
    data = {"papers": [sample_paper_dict]}
    path = tmp_path / "papers.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def empty_papers_json(tmp_path):
    """Create an empty papers.json."""
    path = tmp_path / "papers.json"
    path.write_text('{"papers": []}', encoding="utf-8")
    return path
