"""CLI tests: run the real pipeline end-to-end through main() with
injected fake LLM / search clients (no network, no API keys)."""

import pytest
from langchain_core.language_models import FakeListChatModel

import auto_knowledge_base.cli as cli

from .conftest import FakeSearchClient

ANALYSIS = "SUMMARY: s.\nCATEGORY: Cat\nTAGS: t"


@pytest.fixture
def patched_clients(monkeypatch, fake_results):
    """Replace the real OpenAI/Tavily factories with in-process fakes."""
    monkeypatch.setattr(cli, "_make_llm", lambda model: FakeListChatModel(
        responses=["refined topic", "kw1\nkw2", ANALYSIS, ANALYSIS]))
    monkeypatch.setattr(cli, "_make_search",
                        lambda: FakeSearchClient(fake_results))


def test_build_command_end_to_end(tmp_path, patched_clients, capsys):
    rc = cli.main(["build", "--user", "alice", "--kb", "demo",
                   "--topic", "quantum", "--data-root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Saved 2 new article(s)" in out

    # The multi-user layout is created under data_root/<user>/<kb>.
    kb_root = tmp_path / "alice" / "demo"
    assert (kb_root / "README.md").exists()
    assert (kb_root / "index.html").exists()
    assert list((kb_root / "Articles").rglob("*.md"))


def test_build_is_incremental_across_invocations(tmp_path, patched_clients, capsys):
    cli.main(["build", "--user", "alice", "--kb", "demo",
              "--topic", "quantum", "--data-root", str(tmp_path)])
    cli.main(["build", "--user", "alice", "--kb", "demo",
              "--topic", "quantum", "--data-root", str(tmp_path)])
    out = capsys.readouterr().out
    # Second run finds the same URLs already stored and skips them.
    assert "Saved 0 new article(s), skipped 2 duplicate(s)" in out


def test_agent_command_exits_on_quit(tmp_path, patched_clients, monkeypatch):
    # Feed a single "quit" so the REPL terminates without invoking the LLM.
    monkeypatch.setattr("builtins.input", lambda *a: "quit")
    rc = cli.main(["agent", "--user", "alice", "--kb", "demo",
                   "--data-root", str(tmp_path)])
    assert rc == 0


def test_graph_command_writes_mermaid_source(tmp_path, capsys):
    out = tmp_path / "pipeline.mmd"
    rc = cli.main(["graph", "--output", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    # All six pipeline nodes must appear in the rendered topology.
    for node in ("optimize_topic", "generate_keywords", "search",
                 "dedupe", "summarize_and_save", "update_index"):
        assert node in text
    assert f"Pipeline graph written to {out}" in capsys.readouterr().out


def test_graph_command_writes_png(tmp_path, monkeypatch):
    # PNG rendering calls the mermaid.ink web service; stub out that network I/O.
    from langchain_core.runnables.graph import Graph
    monkeypatch.setattr(Graph, "draw_mermaid_png",
                        lambda self, **kwargs: b"\x89PNG fake bytes")
    out = tmp_path / "pipeline.png"
    rc = cli.main(["graph", "-o", str(out)])
    assert rc == 0
    assert out.read_bytes().startswith(b"\x89PNG")


def test_graph_command_rejects_unknown_extension(tmp_path, capsys):
    out = tmp_path / "pipeline.svg"
    rc = cli.main(["graph", "--output", str(out)])
    assert rc == 2
    assert not out.exists()
    assert "Unsupported output format" in capsys.readouterr().err


def test_missing_command_is_an_error():
    with pytest.raises(SystemExit):
        cli.main([])
