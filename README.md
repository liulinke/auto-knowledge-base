# auto-knowledge-base — Automated Web Collection & Continuously Growing Local Knowledge Base

## Overview

`auto-knowledge-base` turns a research topic into a structured, offline-browsable local
knowledge base. An LLM refines your topic, generates search keywords, collects
the top web results, deduplicates against what is already stored, writes each
article as clean Markdown with an **LLM-generated summary** in its sidecar
metadata, and rebuilds an offline `index.html` viewer. Built on
**deepagents**, **LangChain** and **LangGraph**.

**A knowledge base is never "finished" — it grows continuously.** The backend
keeps one folder per user and one folder per knowledge base, and every run is
incremental: you can come back tomorrow, next week, or after a related idea
strikes, run another query against the same `--user`/`--kb`, and only genuinely
new articles are added. Deduplication works at two levels (source URL and
content hash, both persisted in `_Metadata/` sidecar files), so repeated or
overlapping queries never create duplicates.

[中文说明 (Chinese version)](README_CN.md)

## Requirements

- Python >= 3.11
- [`uv`](https://docs.astral.sh/uv/) (recommended package manager)
- For real collection runs (not needed for tests):
  - `OPENAI_API_KEY` — LLM (topic optimization, keywords, summaries; default model `gpt-4o-mini`)
  - `TAVILY_API_KEY` — web search

## Setup

```bash
# One command: creates the virtual environment and installs all
# dependencies including the dev group (pytest etc.)
uv sync

# API keys: copy the sample and fill in your keys (.env is git-ignored
# and loaded automatically at startup)
cp .env.sample .env
```

All later commands go through `uv run ...` — no manual venv activation needed.

## Usage

### Collection pipeline (LangGraph) — build, then keep growing

Each `build` run executes the deterministic flow (optimize topic → generate
keywords → search → dedupe → summarize & save → rebuild index) **against the
same knowledge base folder**, so you grow it query by query over time:

```bash
# Day 1 — create the knowledge base with a first topic
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction" \
  --max-results 5
# => Saved 8 new article(s), skipped 0 duplicate(s).

# Day 2 — same kb, a follow-up angle: only new material is added
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "surface codes and fault tolerance"
# => Saved 5 new article(s), skipped 3 duplicate(s).   <- overlap auto-skipped

# Weeks later — refresh the original topic to pick up recent results
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction 2026 advances"
# => Saved 2 new article(s), skipped 6 duplicate(s).
```

After every run, `README.md` and `index.html` are rebuilt to reflect the
*accumulated* contents — articles from all runs appear together, organized by
category. Nothing is ever re-downloaded or duplicated: URLs and content hashes
already recorded in `_Metadata/` are skipped automatically.

### Interactive deep agent (deepagents) — conversational growth

The agent is the other way to keep extending an existing knowledge base: it
first inspects what the kb **already contains**, then plans searches that fill
the gaps, saving only new summarized articles:

```bash
uv run auto-knowledge-base agent --user alice --kb quantum-computing
you> find recent surveys about surface codes
agent> Saved 4 new articles under "Surface Codes" ...
you> now add material about logical qubit demonstrations
agent> The kb already covers 2 of the top results; saved 3 new articles ...
```

### Pipeline graph image

Render the LangGraph pipeline topology to a file (no API keys needed):

```bash
uv run auto-knowledge-base graph --output pipeline.png   # image, rendered via mermaid.ink (needs network)
uv run auto-knowledge-base graph --output pipeline.mmd   # Mermaid source, fully offline
```

### Output layout

```
kb_data/<user>/<kb>/
├── README.md            # AI-assembled overview, keyword scope, article list
├── index.html           # double-click: offline tree / search / md preview
├── Articles/<Category>/<slug>.md
├── Attachments/         # media assets (kept separate from text)
├── Data/Raw/  Data/Processed/
└── _Metadata/<Category>/<slug>.json   # url, hash, tags, LLM summary, ...
```

Open `kb_data/<user>/<kb>/index.html` directly in a browser — it is fully
offline (no CDN), with a collapsible category tree, search box and Markdown
preview.

The full layout specification — file formats, the `_Metadata/` sidecar JSON
schema, query recipes for AI agents, and the invariants they can rely on — is
in [docs/knowledge-base-structure.md](docs/knowledge-base-structure.md).

### Configuration

All settings can also be placed in `.env` (see `.env.sample`). Real
environment variables take precedence over `.env` values.

| Setting | Flag | Env var | Default |
| --- | --- | --- | --- |
| Storage root | `--data-root` | `AUTO_KB_DATA_ROOT` | `./kb_data` |
| Model | `--model` | `AUTO_KB_MODEL` | `gpt-4o-mini` |
| OpenAI key | — | `OPENAI_API_KEY` | required for real runs |
| Tavily key | — | `TAVILY_API_KEY` | required for real runs |

## Testing

Unit tests use fake LLM and search clients — no network or API keys needed.

```bash
uv run pytest                      # run all tests
uv run pytest -v --tb=short       # verbose
uv run pytest tests/test_pipeline.py   # single file
uv run pytest --cov=auto_knowledge_base --cov-report=term   # with coverage
```

Current suite: 45 tests, ~91 % coverage. Key scenarios covered:

- multi-user folder isolation and path-traversal safety
- URL-level and content-hash-level deduplication across incremental runs
- mirrored `_Metadata/` sidecar files with LLM summaries
- end-to-end LangGraph pipeline run (and a second run skipping duplicates)
- offline `index.html` generation (embedded data, no CDN, `</script>` escaping)
- deepagents tool wiring (search / save / list / rebuild-index)

