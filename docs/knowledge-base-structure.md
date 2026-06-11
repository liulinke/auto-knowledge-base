# Knowledge Base Folder Structure

This document describes the on-disk layout of a single knowledge base so that
an AI agent (or any program) can navigate and query it without prior knowledge
of this project. The layout is produced and maintained by
`src/auto_knowledge_base/storage.py` and `indexer.py`.

## Where knowledge bases live

All knowledge bases sit under a data root (default: `kb_data/`), organized as
**one folder per user, one folder per knowledge base**:

```
<data_root>/<user_id>/<kb_name>/
```

Example: `kb_data/alice/quantum-computing/`. Both `user_id` and `kb_name` are
slugified (lowercased, unsafe characters replaced) so they are always valid
path segments.

## Layout of one knowledge base

```
<data_root>/<user_id>/<kb_name>/
├── README.md                          # Human/AI-readable entry point and table of contents
├── index.html                         # Offline graphical browser (tree, tags, search, preview)
├── Articles/
│   └── <Category>/
│       └── <article-slug>.md          # One collected article, converted to Markdown
├── _Metadata/
│   └── <Category>/
│       └── <article-slug>.json        # Sidecar metadata; mirrors the Articles/ path exactly
├── Attachments/                       # Reserved for binary attachments (images, PDFs)
└── Data/
    ├── Raw/                           # Reserved for raw fetched payloads
    └── Processed/                     # Reserved for intermediate processing artifacts
```

`Attachments/` and `Data/` are created as part of the standard skeleton but are
currently empty; all queryable content lives in `Articles/`, `_Metadata/`, and
`README.md`.

## README.md — start here

`README.md` is regenerated from scratch after every collection run, so it
always reflects the current state. It contains, in order:

1. **Topic** — the research topic this knowledge base covers.
2. **Last updated** — ISO-8601 timestamp of the last run.
3. **Overview** (optional) — a prose summary of the knowledge base.
4. **Search keyword scope** — the search keywords used to collect content.
5. **Contents** — total article count, a per-category count table, then for
   each category a list of `[title](relative/path.md) — summary` entries
   linking to every article.

An agent that only reads `README.md` already gets every article's title,
category, summary, and relative path.

## Articles/

Articles are grouped into one subdirectory per **category** (an LLM-assigned
sub-topic, e.g. `Quantum-Error-Correction`). Each article is a single Markdown
file with this shape:

```markdown
# <Article title>

> Source: <original URL>

<article body converted from the web page>
```

File names are slugified titles. On a name collision, a numeric suffix is
appended (`foo.md`, `foo-2.md`, `foo-3.md`), so two distinct articles never
share a path.

## _Metadata/ — the machine-readable index

For every `Articles/<Category>/<slug>.md` there is a sidecar
`_Metadata/<Category>/<slug>.json` (same category directory, same file stem).
These sidecars are the **single source of truth** for deduplication and
indexing. Schema (see `ArticleMetadata` in `src/auto_knowledge_base/models.py`):

| Field | Type | Meaning |
| --- | --- | --- |
| `url` | string | Original source URL (unique within the knowledge base) |
| `title` | string | Article title |
| `content_hash` | string | MD5 of the Markdown body; used for content-level dedup |
| `crawl_time` | string | ISO-8601 timestamp of when the article was collected |
| `tags` | string[] | LLM-assigned topical tags |
| `category` | string | Sub-topic; matches the subdirectory under `Articles/` |
| `summary` | string | LLM-generated summary of the article |
| `source_keywords` | string[] | Search keywords that led to this article |
| `article_relpath` | string | Article path relative to the knowledge base root, e.g. `Articles/Quantum-Computing/Threshold-theorem-Wikipedia.md` |

Example:

```json
{
  "url": "https://en.wikipedia.org/wiki/Threshold_theorem",
  "title": "Threshold theorem - Wikipedia",
  "content_hash": "c2e257716b3bf2e57418a896c9287b8c",
  "crawl_time": "2026-06-11T03:50:27+00:00",
  "tags": ["threshold theorem", "quantum error correction"],
  "category": "Quantum Computing",
  "summary": "The threshold theorem states that ...",
  "source_keywords": ["Quantum fault tolerance methods"],
  "article_relpath": "Articles/Quantum-Computing/Threshold-theorem-Wikipedia.md"
}
```

Note: `category` in the JSON is the original (unslugified) name, while the
directory name is its slug — resolve articles via `article_relpath`, not by
reconstructing paths from `category`.

## index.html

A self-contained offline viewer rebuilt after every run. Open it in a browser
for a folder tree, tag filters, full-text search, and Markdown preview. It is
intended for humans; agents should query the files directly instead.

## How an AI agent should query a knowledge base

1. **Get an overview**: read `README.md` for the topic, keyword scope,
   categories, and the full annotated article list.
2. **Structured queries** (filter by tag, category, date, source): load every
   JSON file under `_Metadata/` (recursive glob `_Metadata/**/*.json`) and
   filter on its fields, then read the file at `article_relpath` for matches.
3. **Full-text search**: grep over `Articles/**/*.md`; map a hit back to its
   metadata by swapping `Articles/` for `_Metadata/` and `.md` for `.json`.
4. **Check whether a source is already collected**: compare against the `url`
   or `content_hash` values across all sidecars — this is exactly how the
   pipeline deduplicates incremental runs.
5. **Cite sources**: every article's second line (`> Source: <URL>`) and its
   sidecar `url` field give the original provenance.

## Invariants an agent can rely on

- Every article under `Articles/` has exactly one sidecar under `_Metadata/`
  at the mirrored path.
- `url` and `content_hash` are unique across one knowledge base (enforced by
  dedup at collection time).
- `README.md` and `index.html` are derived files, always consistent with the
  sidecars after a run; never edit them by hand.
- All paths inside the knowledge base are relative to its root, so the whole
  folder can be moved or copied freely.
