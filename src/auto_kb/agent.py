"""Interactive research agent built with deepagents.

Unlike the deterministic pipeline, the deep agent plans its own
multi-step research: it inspects what the knowledge base already
contains, runs additional searches, summarizes and saves new articles,
then rebuilds the index. This is the mode for incrementally growing an
existing knowledge base with follow-up queries.
"""

import json

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from .indexer import generate_index_html, generate_readme
from .models import ArticleMetadata
from .search import SearchClient
from .storage import KnowledgeBaseStorage
from .utils import content_hash, now_iso

SYSTEM_PROMPT = """You are a research librarian maintaining a local knowledge base.

Workflow for every user request:
1. Call list_saved_articles first to see what the knowledge base already covers.
2. Plan search keywords that fill the gaps, then call internet_search.
3. For each useful result, write a 2-3 sentence summary yourself, pick a short
   sub-topic category and a few tags, then call save_article. Never save an
   article without a summary.
4. When done saving, call rebuild_index exactly once.

Rules:
- Skip results whose URL is already in the knowledge base (save_article
  reports duplicates; do not retry them).
- Article bodies must be Markdown.
- Be selective: only save substantive, on-topic articles.
"""


def create_kb_agent(llm: BaseChatModel, search_client: SearchClient,
                    storage: KnowledgeBaseStorage, max_results: int = 5):
    """Build the deep agent wired to this user's knowledge base folder."""
    storage.init_layout()

    @tool
    def internet_search(query: str) -> str:
        """Search the web. Returns a JSON list of {url, title, snippet, content}."""
        results = search_client.search(query, max_results=max_results)
        payload = [{
            "url": r.url, "title": r.title, "snippet": r.snippet,
            # Truncate page text so a single result cannot blow the context.
            "content": (r.raw_content or "")[:6000],
        } for r in results]
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def save_article(url: str, title: str, markdown_body: str, summary: str,
                     category: str, tags: list[str]) -> str:
        """Save one article into the knowledge base with its metadata.
        `summary` is required and must be your own 2-3 sentence summary."""
        if storage.is_duplicate_url(url):
            return f"DUPLICATE: {url} is already in the knowledge base, skipped."
        h = content_hash(markdown_body)
        if storage.is_duplicate_hash(h):
            return f"DUPLICATE: identical content already stored, skipped {url}."
        meta = ArticleMetadata(
            url=url, title=title, content_hash=h, crawl_time=now_iso(),
            tags=tags, category=category, summary=summary,
        )
        path = storage.save_article(
            f"# {title}\n\n> Source: {url}\n\n{markdown_body}\n", meta)
        return f"SAVED: {path.relative_to(storage.root)}"

    @tool
    def list_saved_articles() -> str:
        """List articles already in the knowledge base (title, url, category)."""
        metas = storage.list_metadata()
        if not metas:
            return "The knowledge base is empty."
        return json.dumps([{
            "title": m.title, "url": m.url, "category": m.category,
        } for m in metas], ensure_ascii=False)

    @tool
    def rebuild_index(topic: str) -> str:
        """Rebuild README.md and index.html. Call once after saving articles."""
        generate_readme(storage, topic=topic, keywords=[])
        generate_index_html(storage)
        return "Index rebuilt."

    return create_deep_agent(
        model=llm,
        tools=[internet_search, save_article, list_saved_articles, rebuild_index],
        system_prompt=SYSTEM_PROMPT,
    )
