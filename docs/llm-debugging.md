# Inspecting LLM Input & Output

Every LLM call in this project (topic optimization, keyword generation,
quality check, article analysis in the pipeline; every turn of the deep
agent) goes through LangChain, so all of them can be inspected with the
`--debug` flag on the `build` and `agent` commands:

```bash
--debug console    # print every prompt and response to the terminal
--debug langfuse   # send full traces to a (self-hosted) Langfuse server
```

Use `console` for a quick one-off look. Use `langfuse` — an open-source,
self-hostable alternative to LangSmith — when you want a persistent,
searchable record of real runs with token counts and latency.

## Option 1: console mode

No setup required:

```bash
uv run auto-knowledge-base build \
  --user alice --kb quantum-computing \
  --topic "quantum error correction" \
  --debug console
```

This flips LangChain's global debug switch, which dumps every chain/LLM
input and output to stdout as the graph executes. Expect a lot of text —
each article triggers a quality-check call and an analysis call on top of
the topic/keyword calls.

## Option 2: Langfuse (Docker + web UI)

### 1. Start a local Langfuse server with Docker

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```

This starts Langfuse and its dependencies (Postgres, ClickHouse, Redis,
MinIO). Wait until `docker compose ps` shows the containers as healthy,
then open <http://localhost:3000>.

### 2. Create a project and API keys

In the web UI:

1. Sign up (first user on a fresh instance; data stays on your machine).
2. Create an **Organization**, then a **Project** (e.g. `auto-knowledge-base`).
3. Go to **Project Settings → API Keys → Create new API keys** and copy the
   public key (`pk-lf-...`) and secret key (`sk-lf-...`).

### 3. Configure this project

Add the keys to your `.env` (templates are already in `.env.sample`):

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

### 4. Run with tracing enabled

```bash
# Pipeline run
uv run auto-knowledge-base build \
  --user alice --kb quantum-computing \
  --topic "quantum error correction" \
  --debug langfuse

# Interactive agent session
uv run auto-knowledge-base agent \
  --user alice --kb quantum-computing \
  --debug langfuse
```

Traces are buffered and flushed automatically before the command exits, so
short runs lose nothing.

### 5. Check the results in the web UI

Open <http://localhost:3000>, select your project, then go to **Tracing →
Traces**. Each `build` run appears as one trace; click it to see:

- the tree of LangGraph nodes (`optimize_topic` → `generate_keywords` →
  `search` → `dedupe` → `summarize_and_save` → `update_index`);
- one **Generation** entry per LLM call, with the exact prompt sent and the
  raw model response side by side;
- token usage, cost estimate, model name, and latency per call.

For agent sessions, each conversation turn is a trace showing the system
prompt, the tool calls the agent decided to make (`internet_search`,
`save_article`, ...), and the final reply.

The **Dashboard** tab aggregates cost/latency over time, which is useful
once a knowledge base is grown by many incremental runs.

## How it works

`--debug console` calls `langchain_core.globals.set_debug(True)`.
`--debug langfuse` attaches Langfuse's LangChain `CallbackHandler` via
`config={"callbacks": [...]}` when invoking the graph, and LangGraph
propagates it to every LLM call inside the nodes; the handler reads the
`LANGFUSE_*` variables from the environment. See `_debug_callbacks()` in
`src/auto_knowledge_base/cli.py`.

## Troubleshooting

- **No traces appear**: check the three `LANGFUSE_*` variables are set in
  `.env` and that `LANGFUSE_HOST` matches the server address; verify the
  server is up with `docker compose ps`.
- **Auth errors in the console**: the public/secret keys belong to one
  project — regenerate them in Project Settings if in doubt.
- **Port 3000 already in use**: edit the `ports` mapping for the
  `langfuse-web` service in Langfuse's `docker-compose.yml` and update
  `LANGFUSE_HOST` accordingly.
