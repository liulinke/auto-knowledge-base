"""CLI tests: run the real pipeline end-to-end through main() with
injected fake LLM / search clients (no network, no API keys)."""

import pytest
from langchain_core.language_models import FakeListChatModel

import auto_kb.cli as cli

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


def test_missing_command_is_an_error():
    with pytest.raises(SystemExit):
        cli.main([])
