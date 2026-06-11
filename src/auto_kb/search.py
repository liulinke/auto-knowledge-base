"""Search backend abstraction.

The pipeline and the deep agent only depend on the `SearchClient`
protocol, so tests can inject an in-process fake and production code
can swap Tavily for any other engine.
"""

from typing import Protocol

from .models import SearchResult


class SearchClient(Protocol):
    """Minimal interface every search backend must implement."""

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...


class TavilySearchClient:
    """Tavily-backed implementation. Requires TAVILY_API_KEY in the env.

    `include_raw_content=True` asks Tavily for the full page text, which
    saves us an extra HTTP fetch for most results.
    """

    def __init__(self, api_key: str | None = None):
        # Imported lazily so unit tests never need the tavily package configured.
        from tavily import TavilyClient

        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        resp = self._client.search(
            query=query,
            max_results=max_results,
            include_raw_content=True,
        )
        results = []
        for item in resp.get("results", []):
            results.append(SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                raw_content=item.get("raw_content") or None,
                source_keyword=query,
            ))
        return results
