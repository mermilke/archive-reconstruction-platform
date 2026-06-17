# Contributing

Thanks for your interest! This is a small, focused toolkit, and a few
conventions keep it that way.

## The hard rule: a zero-dependency core

**The runtime core depends on the Python standard library only.** Do not add a
third-party package to `dependencies` in `pyproject.toml`. This is the project's
defining constraint — the "core deps: 0" badge must stay true.

There are exactly two sanctioned, **opt-in** exceptions, both behind optional
extras that no core path imports:

- `arc organize` may call the Claude API (via stdlib `urllib` — *not* the
  `anthropic` SDK), and only when `ANTHROPIC_API_KEY` is set.
- the `[pdf]` extra (`pypdf`) makes PDF text extraction more robust; the stdlib
  reader is always the default.

If you think a feature needs a new runtime dependency, open an issue first.

## Dev setup

Python 3.9+.

```bash
git clone https://github.com/mermilke/archive-reconstruction-platform
cd archive-reconstruction-platform
python -m pip install -e ".[dev]"
```

The `[dev]` extra installs `ruff`, `mypy`, and `coverage`. (The package itself
still installs with zero dependencies — `pip install -e .`.)

## Run the tests

The suite uses a **custom runner**, not pytest. It auto-discovers every
`tests/test_*.py`:

```bash
python tests/run_all.py
```

Each test file is also runnable on its own (`python tests/test_dedup.py`).

## Lint and type-check

CI runs both; please run them before opening a PR:

```bash
ruff check
mypy
```

`ruff` and `mypy` read their configuration from `pyproject.toml`. Fix findings
rather than suppressing them; if a suppression is genuinely warranted, keep it
narrow and add a comment explaining why.

## Coverage (optional)

Because the runner isn't pytest, measure coverage by running it under
`coverage`:

```bash
coverage run tests/run_all.py
coverage report
```

## Conventions

- **Every feature ships with a test.** Every "messy input" feature also ships a
  messy fixture under `tests/fixtures/`.
- **Keep modules small and single-purpose; the CLI stays thin.** The clever part
  is the *idea* (branch-aware dedup) — keep the code clear.
- **All example data is fully synthetic** (themed around the fictional "Voltera"
  company). Never add real names, companies, filenames, or message content.
- **CLI stdout must be ASCII** — the generated HTML is UTF-8, but console output
  has to survive a Windows code page, so use `[keep]`/`[del]`, "subset of", etc.,
  not Unicode glyphs.

## Submitting changes

1. Branch off `main`.
2. Make the change with a test.
3. Ensure `python tests/run_all.py`, `ruff check`, and `mypy` all pass.
4. Open a PR describing the change and why.
