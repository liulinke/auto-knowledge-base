"""Shared fakes: an in-process search client and canned search data.

No test in this suite touches the network or needs an API key.
"""

import pytest

from auto_kb.models import SearchResult
from auto_kb.storage import KnowledgeBaseStorage


class FakeSearchClient:
    """Returns predefined results regardless of the query."""

    def __init__(self, results: list[SearchResult]):
        self._results = results
        self.queries: list[str] = []  # recorded for assertions

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return self._results[:max_results]


@pytest.fixture
def storage(tmp_path):
    """A fresh knowledge base under a temp directory."""
    return KnowledgeBaseStorage(tmp_path, "alice", "test-kb")


@pytest.fixture
def fake_results():
    return [
        SearchResult(
            url="https://example.com/a",
            title="Quantum Error Correction Basics",
            snippet="intro to QEC",
            raw_content="Quantum error correction protects qubits from noise. " * 5,
            source_keyword="quantum error correction",
        ),
        SearchResult(
            url="https://example.com/b",
            title="Surface Codes Explained",
            snippet="surface codes",
            raw_content="Surface codes are a leading approach to fault tolerance. " * 5,
            source_keyword="surface codes",
        ),
    ]
