"""Application configuration resolved from .env, environment and CLI flags.

API keys (OPENAI_API_KEY, TAVILY_API_KEY) live in a git-ignored `.env`
file — see `.env.sample` for the template. `load_env()` must run before
any client is constructed so the keys are present in os.environ.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Default LLM; override via --model or AUTO_KB_MODEL.
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_DATA_ROOT = "kb_data"


def load_env() -> None:
    """Load `.env` from the current working directory (and parents).

    Existing environment variables win over .env values, so deployment
    overrides keep working. usecwd=True anchors the search at the
    invocation directory (not this module's install location), which is
    what users expect when they run `auto-knowledge-base` inside their project.
    """
    load_dotenv(find_dotenv(usecwd=True), override=False)


@dataclass
class AppConfig:
    """Runtime settings shared by the CLI entry points."""

    data_root: Path = field(default_factory=lambda: Path(
        os.environ.get("AUTO_KB_DATA_ROOT", DEFAULT_DATA_ROOT)))
    model_name: str = field(default_factory=lambda: os.environ.get(
        "AUTO_KB_MODEL", DEFAULT_MODEL))
    # How many search results to keep per keyword.
    max_results: int = 5
