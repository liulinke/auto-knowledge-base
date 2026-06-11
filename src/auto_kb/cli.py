"""Command line entry points.

    auto-kb build --user alice --kb quantum --topic "quantum error correction"
    auto-kb agent --user alice --kb quantum

API keys (OPENAI_API_KEY, TAVILY_API_KEY) are read from a `.env` file
in the working directory — copy `.env.sample` to `.env` and fill it in.
Real clients are constructed only at run time so the rest of the
package stays import-safe without keys.
"""

import argparse
import sys

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


def cmd_build(args: argparse.Namespace) -> int:
    """Run the deterministic LangGraph pipeline once (incremental)."""
    from .pipeline import build_pipeline

    storage = KnowledgeBaseStorage(args.data_root, args.user, args.kb)
    pipeline = build_pipeline(_make_llm(args.model), _make_search(),
                              storage, max_results=args.max_results)
    result = pipeline.invoke({"topic": args.topic})

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
        state = agent.invoke({"messages": messages})
        messages = state["messages"]
        print(f"agent> {messages[-1].content}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Pull API keys and overrides from .env before anything reads os.environ.
    load_env()
    cfg = AppConfig()
    parser = argparse.ArgumentParser(prog="auto-kb",
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
