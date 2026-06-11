"""Command line entry points.

    auto-knowledge-base build --user alice --kb quantum --topic "quantum error correction"
    auto-knowledge-base agent --user alice --kb quantum
    auto-knowledge-base graph --output pipeline.png

API keys (OPENAI_API_KEY, TAVILY_API_KEY) are read from a `.env` file
in the working directory — copy `.env.sample` to `.env` and fill it in.
Real clients are constructed only at run time so the rest of the
package stays import-safe without keys.
"""

import argparse
import sys
from pathlib import Path

from .config import AppConfig, load_env
from .storage import KnowledgeBaseStorage


def _make_llm(model_name: str):
    # Imported lazily: tests and offline tooling never need the real client.
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model_name, max_tokens=4096)


def _make_search():
    from .search import TavilySearchClient
    return TavilySearchClient()


def _add_common_args(p: argparse.ArgumentParser, cfg: AppConfig) -> None:
    p.add_argument("--user", required=True, help="user id (one folder per user)")
    p.add_argument("--kb", required=True, help="knowledge base name (one folder per kb)")
    p.add_argument("--data-root", default=str(cfg.data_root), help="storage root directory")
    p.add_argument("--model", default=cfg.model_name, help="OpenAI model name")
    p.add_argument("--debug", choices=["console", "langfuse"], default=None,
                   help="inspect LLM input/output: 'console' prints every prompt/"
                        "response, 'langfuse' sends traces to a Langfuse server "
                        "(see docs/llm-debugging.md)")


def _debug_callbacks(mode: str | None) -> list:
    """Translate --debug into LangChain callbacks and/or global flags.

    Returns the callback list to pass via `config={"callbacks": ...}` so
    LangGraph propagates it to every LLM call inside the graph.
    """
    if mode == "console":
        # Global switch: dumps every chain/LLM input and output to stdout.
        from langchain_core.globals import set_debug
        set_debug(True)
        return []
    if mode == "langfuse":
        # Reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
        # from the environment (populated from .env by load_env()).
        from langfuse.langchain import CallbackHandler
        return [CallbackHandler()]
    return []


def _flush_debug(mode: str | None) -> None:
    """Flush buffered traces before the process exits (langfuse mode only)."""
    if mode == "langfuse":
        from langfuse import get_client
        get_client().flush()


def cmd_build(args: argparse.Namespace) -> int:
    """Run the deterministic LangGraph pipeline once (incremental)."""
    from .pipeline import build_pipeline

    storage = KnowledgeBaseStorage(args.data_root, args.user, args.kb)
    pipeline = build_pipeline(_make_llm(args.model), _make_search(),
                              storage, max_results=args.max_results)
    callbacks = _debug_callbacks(args.debug)
    result = pipeline.invoke({"topic": args.topic},
                             config={"callbacks": callbacks})
    _flush_debug(args.debug)

    saved = result.get("saved", [])
    print(f"Knowledge base: {storage.root}")
    print(f"Optimized topic: {result.get('optimized_topic', '')}")
    print(f"Keywords: {', '.join(result.get('keywords', []))}")
    print(f"Saved {len(saved)} new article(s), skipped {result.get('skipped', 0)} duplicate(s).")
    for rel in saved:
        print(f"  + {rel}")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    """Interactive deepagents REPL for incremental knowledge base growth."""
    from .agent import create_kb_agent

    storage = KnowledgeBaseStorage(args.data_root, args.user, args.kb)
    agent = create_kb_agent(_make_llm(args.model), _make_search(), storage)
    callbacks = _debug_callbacks(args.debug)

    print(f"Knowledge base: {storage.root}")
    print("Type a research request, or 'quit' to exit.")
    messages = []
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in {"quit", "exit"}:
            break
        messages.append({"role": "user", "content": user_input})
        state = agent.invoke({"messages": messages},
                             config={"callbacks": callbacks})
        messages = state["messages"]
        print(f"agent> {messages[-1].content}")
    _flush_debug(args.debug)
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Render the LangGraph pipeline topology to the requested file."""
    from .pipeline import build_pipeline

    # Nodes only touch the LLM/search/storage when invoked, so the graph
    # can be compiled and drawn without API keys or a knowledge base.
    pipeline = build_pipeline(llm=None, search_client=None, storage=None)
    graph = pipeline.get_graph()

    out = Path(args.output)
    suffix = out.suffix.lower()
    if suffix == ".png":
        # Rendered via the mermaid.ink web service; needs network access.
        out.write_bytes(graph.draw_mermaid_png())
    elif suffix == ".mmd":
        out.write_text(graph.draw_mermaid(), encoding="utf-8")
    else:
        print(f"Unsupported output format '{suffix or args.output}': "
              "use .png (image) or .mmd (Mermaid source).", file=sys.stderr)
        return 2
    print(f"Pipeline graph written to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Pull API keys and overrides from .env before anything reads os.environ.
    load_env()
    cfg = AppConfig()
    parser = argparse.ArgumentParser(prog="auto-knowledge-base",
                                     description="Automated web collection & local knowledge base builder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="run the collection pipeline once")
    _add_common_args(p_build, cfg)
    p_build.add_argument("--topic", required=True, help="research topic to collect")
    p_build.add_argument("--max-results", type=int, default=cfg.max_results,
                         help="search results to keep per keyword")
    p_build.set_defaults(func=cmd_build)

    p_agent = sub.add_parser("agent", help="interactive deep agent session")
    _add_common_args(p_agent, cfg)
    p_agent.set_defaults(func=cmd_agent)

    p_graph = sub.add_parser("graph", help="render the pipeline graph to a file")
    p_graph.add_argument("--output", "-o", required=True,
                         help="output file name: .png (image) or .mmd (Mermaid source)")
    p_graph.set_defaults(func=cmd_graph)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
