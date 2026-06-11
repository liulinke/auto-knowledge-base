"""Deterministic collection pipeline built on a LangGraph StateGraph.

    optimize_topic -> generate_keywords -> search -> dedupe
        -> summarize_and_save -> update_index

The LLM and the search backend are injected, so the whole graph runs
in unit tests with fakes (no network, no API key).
"""

from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from .indexer import generate_index_html, generate_readme
from .models import ArticleMetadata, SearchResult
from .search import SearchClient
from .storage import KnowledgeBaseStorage
from .utils import content_hash, fetch_url, html_to_markdown, now_iso


class PipelineState(TypedDict, total=False):
    """State carried between graph nodes."""

    topic: str                       # raw user topic
    optimized_topic: str             # LLM-refined topic
    keywords: list[str]              # generated search keywords
    search_results: list[SearchResult]
    saved: list[str]                 # relpaths of newly saved articles
    skipped: int                     # duplicates skipped in this run


OPTIMIZE_PROMPT = (
    "You are a research assistant. Rewrite and expand the user's raw topic "
    "into one precise, search-friendly research topic statement. "
    "Reply with the refined topic only, no explanations.\n\nRaw topic: {topic}"
)

KEYWORDS_PROMPT = (
    "Generate 3 to 6 precise web search keywords/phrases for the research "
    "topic below. Reply with one keyword per line, nothing else.\n\n"
    "Topic: {topic}"
)

ANALYZE_PROMPT = (
    "Analyze the article below and reply EXACTLY in this format:\n"
    "SUMMARY: <2-3 sentence summary>\n"
    "CATEGORY: <one short sub-topic name>\n"
    "TAGS: <comma separated tags>\n\n"
    "Title: {title}\n\nArticle:\n{body}"
)


def _llm_text(llm: BaseChatModel, prompt: str) -> str:
    """Invoke the model and return plain text content."""
    msg = llm.invoke(prompt)
    return msg.content if isinstance(msg.content, str) else str(msg.content)


def parse_article_analysis(text: str, body: str) -> tuple[str, str, list[str]]:
    """Parse the SUMMARY/CATEGORY/TAGS line protocol with safe fallbacks.

    The pipeline must never crash on a malformed LLM reply, so missing
    fields fall back to a body excerpt / "General" / no tags.
    """
    summary, category, tags = "", "General", []
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("SUMMARY:"):
            summary = stripped[len("SUMMARY:"):].strip()
        elif upper.startswith("CATEGORY:"):
            category = stripped[len("CATEGORY:"):].strip() or "General"
        elif upper.startswith("TAGS:"):
            tags = [t.strip() for t in stripped[len("TAGS:"):].split(",") if t.strip()]
    if not summary:
        summary = body[:200].replace("\n", " ").strip()
    return summary, category, tags


def build_pipeline(llm: BaseChatModel, search_client: SearchClient,
                   storage: KnowledgeBaseStorage, max_results: int = 5):
    """Assemble and compile the six-node collection graph."""

    def optimize_topic(state: PipelineState) -> PipelineState:
        refined = _llm_text(llm, OPTIMIZE_PROMPT.format(topic=state["topic"])).strip()
        return {"optimized_topic": refined or state["topic"]}

    def generate_keywords(state: PipelineState) -> PipelineState:
        raw = _llm_text(llm, KEYWORDS_PROMPT.format(topic=state["optimized_topic"]))
        # One keyword per line; tolerate bullet markers the model may add.
        keywords = [ln.strip().lstrip("-*0123456789. ").strip()
                    for ln in raw.splitlines() if ln.strip()]
        return {"keywords": keywords or [state["optimized_topic"]]}

    def search(state: PipelineState) -> PipelineState:
        # Merge results across keywords, keeping the first hit per URL.
        seen: dict[str, SearchResult] = {}
        for kw in state["keywords"]:
            for r in search_client.search(kw, max_results=max_results):
                if r.url and r.url not in seen:
                    seen[r.url] = r
        return {"search_results": list(seen.values())}

    def dedupe(state: PipelineState) -> PipelineState:
        # URL-level dedup against existing sidecar metadata (incremental runs).
        known = storage.known_urls()
        fresh = [r for r in state["search_results"] if r.url not in known]
        skipped = len(state["search_results"]) - len(fresh)
        return {"search_results": fresh, "skipped": skipped}

    def summarize_and_save(state: PipelineState) -> PipelineState:
        storage.init_layout()
        known_hashes = storage.known_hashes()
        saved: list[str] = []
        skipped = state.get("skipped", 0)

        for result in state["search_results"]:
            # Prefer the search engine's raw content; fetch the page otherwise.
            body = result.raw_content
            title = result.title
            if not body:
                html = fetch_url(result.url)
                if html is None:
                    skipped += 1
                    continue
                body = html_to_markdown(html)
            if not body.strip():
                skipped += 1
                continue

            # Content-level dedup catches the same article behind a new URL.
            h = content_hash(body)
            if h in known_hashes:
                skipped += 1
                continue

            analysis = _llm_text(llm, ANALYZE_PROMPT.format(
                title=title or result.url, body=body[:8000]))
            summary, category, tags = parse_article_analysis(analysis, body)

            meta = ArticleMetadata(
                url=result.url,
                title=title or result.url,
                content_hash=h,
                crawl_time=now_iso(),
                tags=tags,
                category=category,
                summary=summary,
                source_keywords=[result.source_keyword] if result.source_keyword else [],
            )
            markdown = f"# {meta.title}\n\n> Source: {meta.url}\n\n{body}\n"
            path = storage.save_article(markdown, meta)
            known_hashes.add(h)
            saved.append(str(path.relative_to(storage.root)))

        return {"saved": saved, "skipped": skipped}

    def update_index(state: PipelineState) -> PipelineState:
        generate_readme(storage, topic=state.get("optimized_topic", state["topic"]),
                        keywords=state.get("keywords", []))
        generate_index_html(storage)
        return {}

    graph = StateGraph(PipelineState)
    graph.add_node("optimize_topic", optimize_topic)
    graph.add_node("generate_keywords", generate_keywords)
    graph.add_node("search", search)
    graph.add_node("dedupe", dedupe)
    graph.add_node("summarize_and_save", summarize_and_save)
    graph.add_node("update_index", update_index)

    graph.add_edge(START, "optimize_topic")
    graph.add_edge("optimize_topic", "generate_keywords")
    graph.add_edge("generate_keywords", "search")
    graph.add_edge("search", "dedupe")
    graph.add_edge("dedupe", "summarize_and_save")
    graph.add_edge("summarize_and_save", "update_index")
    graph.add_edge("update_index", END)

    return graph.compile()
