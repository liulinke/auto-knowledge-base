# Project Guidelines

## Language & Comments
- Write all code comments in **English**.
- Comments should explain *why*, not just *what*. One concise line is enough.

## Python Environment
- Use **`uv`** as the primary package manager (not pip, poetry, or conda).
  ```bash
  uv venv          # create virtual environment
  uv pip install   # install packages
  uv run pytest    # run tests
  ```
- Manage dependencies in `pyproject.toml`. Never commit `requirements.txt` unless explicitly requested.

## File Structure
```
project-root/
├── CLAUDE.md
├── README.md
├── .gitignore
├── pyproject.toml
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       └── ...
└── tests/
    ├── __init__.py
    └── test_*.py
```
- Source code lives under `src/<package_name>/`.
- Tests live under `tests/` and mirror the `src/` structure.
- Entry-point scripts go in `src/<package_name>/cli.py` or `__main__.py`.

## Code Structure
- One class / one responsibility per file where practical.
- Prefer plain functions over classes when there is no shared state.
- No global mutable state.
- Use type hints on all function signatures.
- Keep functions short; extract helpers rather than nesting logic deeply.

## .gitignore
Always maintain a `.gitignore` suitable for Python projects. At minimum it must cover:
- `__pycache__/`, `*.pyc`, `*.pyo`
- `.venv/`, `venv/`, `.env`
- `dist/`, `build/`, `*.egg-info/`
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `*.log`, `*.db`, `*.sqlite`
- IDE folders: `.vscode/`, `.idea/`

When bootstrapping a new project, create `.gitignore` before the first commit.

## README
Every project must have a `README.md` that includes:
1. **Overview** — one paragraph describing what the project does.
2. **Requirements** — Python version and any system dependencies.
3. **Setup** — step-by-step using `uv`:
   ```bash
   uv venv && source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```
4. **Usage** — minimal working example (CLI command or Python snippet).
5. **Testing** — how to run tests:
   ```bash
   uv run pytest
   uv run pytest -v --tb=short   # verbose
   uv run pytest tests/test_foo.py  # single file
   ```

## Testing Rules
- **Always write unit tests for every new function or class before marking a task done.**
- Run tests immediately after writing them: `uv run pytest`.
- Test file naming: `tests/test_<module>.py`.
- Use `pytest`; add `pytest` and `pytest-cov` to the `[dev]` dependency group.
- Cover the happy path and at least one edge case / error path per function.
- Do not mock internal modules unless I/O or time is involved — test real behavior.
- Minimum coverage target: **80 %** for new code.

## Workflow
1. Create `.gitignore` before any other file in a new project.
2. Set up `pyproject.toml` with `[project]` and `[project.optional-dependencies] dev = [...]`.
3. Write source code under `src/`.
4. Write corresponding tests under `tests/` **immediately**.
5. Run `uv run pytest` — all tests must pass before moving on.
6. Update `README.md` to reflect any new commands or features.
