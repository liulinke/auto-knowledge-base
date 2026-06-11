"""Pydantic data models shared across the pipeline, agent and storage layers."""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """One hit returned by a search backend.

    `raw_content` is the full page text when the backend provides it
    (e.g. Tavily with include_raw_content=True); otherwise the page is
    fetched over HTTP later in the pipeline.
    """

    url: str
    title: str = ""
    snippet: str = ""
    raw_content: str | None = None
    # The search keyword that produced this hit; kept for provenance.
    source_keyword: str = ""


class ArticleMetadata(BaseModel):
    """Sidecar metadata stored as JSON under `_Metadata/`, mirroring the
    article path under `Articles/`. This is the single source of truth
    for deduplication and for the offline index."""

    url: str
    title: str
    # MD5 of the markdown body; used for content-level dedup.
    content_hash: str
    # ISO-8601 timestamp of when the article was collected.
    crawl_time: str
    tags: list[str] = Field(default_factory=list)
    # Sub-topic name; decides the subdirectory under Articles/.
    category: str = "General"
    # LLM-generated summary of the article (required by spec 5.2).
    summary: str = ""
    # Search keywords that led to this article.
    source_keywords: list[str] = Field(default_factory=list)
    # Article path relative to the knowledge base root, e.g. "Articles/AI/foo.md".
    article_relpath: str = ""
