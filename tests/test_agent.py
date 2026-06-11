"""Tests for the deepagents-based agent: graph construction and tool wiring."""

import json

from langchain_core.language_models import FakeListChatModel

import auto_knowledge_base.agent as agent_mod
from auto_knowledge_base.agent import create_kb_agent

from .conftest import FakeSearchClient


def test_agent_graph_builds(storage, fake_results):
    # Construction must succeed with any BaseChatModel and create the kb layout.
    agent = create_kb_agent(FakeListChatModel(responses=["ok"]),
                            FakeSearchClient(fake_results), storage)
    assert agent is not None
    assert storage.articles_dir.is_dir()


def _capture_agent_tools(storage, search_client):
    """Build the agent while intercepting the tool list passed to deepagents,
    so each tool closure (bound to this storage) can be tested directly."""
    captured = {}
    original = agent_mod.create_deep_agent

    def spy(**kwargs):
        captured["tools"] = {t.name: t for t in kwargs["tools"]}
        return original(**kwargs)

    agent_mod.create_deep_agent = spy
    try:
        agent_mod.create_kb_agent(FakeListChatModel(responses=["ok"]),
                                  search_client, storage)
    finally:
        agent_mod.create_deep_agent = original
    return captured["tools"]


def test_agent_tools_work_against_storage(storage, fake_results):
    """Drive the agent's tools directly (as the LLM would) and verify
    search, save with summary, dedup and index rebuild all hit storage."""
    tools = _capture_agent_tools(storage, FakeSearchClient(fake_results))

    # internet_search returns JSON results from the injected client.
    hits = json.loads(tools["internet_search"].invoke({"query": "qec"}))
    assert hits[0]["url"] == "https://example.com/a"

    # save_article stores body + sidecar with the LLM-provided summary.
    msg = tools["save_article"].invoke({
        "url": "https://example.com/a", "title": "QEC Basics",
        "markdown_body": "QEC body text", "summary": "Agent summary.",
        "category": "Physics", "tags": ["qec"],
    })
    assert msg.startswith("SAVED:")
    metas = storage.list_metadata()
    assert metas[0].summary == "Agent summary."

    # A second save of the same URL is reported as duplicate, not re-saved.
    dup = tools["save_article"].invoke({
        "url": "https://example.com/a", "title": "QEC Basics",
        "markdown_body": "other body", "summary": "s",
        "category": "Physics", "tags": [],
    })
    assert dup.startswith("DUPLICATE:")
    assert len(storage.list_metadata()) == 1

    # list_saved_articles reflects storage; rebuild_index writes entry points.
    listing = json.loads(tools["list_saved_articles"].invoke({}))
    assert listing[0]["title"] == "QEC Basics"
    assert tools["rebuild_index"].invoke({"topic": "QEC"}) == "Index rebuilt."
    assert storage.readme_path.exists()
    assert storage.index_html_path.exists()
