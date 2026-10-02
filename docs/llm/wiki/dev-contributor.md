# Developer and Contributor Guide

**Read when:** The user is modifying `python-client/mip/`, tests, the notebook runner, or preparing commits.

**Skip if:** The user is doing federated analysis in a notebook — use `01-onboarding.md` or `02-analysis-workflow.md` instead.

## Project structure

- `workspace/Welcome.ipynb` — local getting-started notebook
- `workspace/examples/feres_analysis.ipynb` — Feres stroke territory example
- `docs/user/` — canonical user documentation (shipped to workspace `docs/`)
- `python-client/mip/` — library modules (`client.py`, `catalog.py`, `pipeline.py`, etc.)
- `python-client/tests/` — unit tests; `conftest.py` keeps imports stable
- `expected_library.md` — public API contract exercised by `workspace/Welcome.ipynb`

Do not hand-edit generated artifacts in `build/`, `*.egg-info/`, or `__pycache__/`.

When the public API changes, update these together:

- `expected_library.md`
- `docs/user/api-reference.md`
- `docs/llm/wiki/03-mip-client-api.md`

Notebook outputs in `workspace/Welcome.ipynb` should be re-run after API changes. Prefer committed outputs for onboarding notebooks (documented convention).

## Build, test, and development

```bash
uv sync --extra dev
uv run mip-notebook
npm install -g @zed-industries/codex-acp   # mip_jupyter_dev tests import the Codex persona
uv run pytest mip_jupyter_dev python-client/tests -q
uv run python python-client/verify_script.py
```

Discover data models before creating an `AnalysisSet`:

```python
client.catalog().data_model("code", version="x.y")
```

## Coding style

- Python 3, PEP 8, 4-space indentation
- `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` env vars
- Docstrings for public APIs
- Explicit error messages; no hidden network side effects in tests

## Testing guidelines

- `unittest` + `unittest.mock` patching `requests.Session`
- Files: `test_*.py`; methods: `test_<behavior>`
- No live HTTP in tests
- Add a regression test with every behavior fix in `mip`

## Commit and PR guidelines

- Concise imperative commit subjects, e.g. `fix(client): handle expired token refresh`
- One logical change per commit
- PRs: what changed, why, test commands, config/env impacts
- Notebook/UX changes: screenshots or output snippets

## Security

Never commit credentials. Use `PLATFORM_BACKEND_URL`, `PLATFORM_TOKEN`, `MIP_TOKEN`, `PLATFORM_BACKEND_TIMEOUT`, and `PLATFORM_BACKEND_ALLOW_REDIRECTS`.

**Next file:** The specific `python-client/mip/` module under change.
