# Conventions

## Code

- ruff formats and lints (`pyproject.toml`), line length 100. mypy strict.
- Package layout: `src/xclean/`. Sources in `sources/`, content types in `content_types/`.
- Only the X client talks HTTP. Only the CLI prints.
- Paths follow XDG on macOS and Linux (`xclean.paths`). Never put tokens in the config folder.

## Tests

- What to test and how: `docs/testing.md`. Below: xclean specifics.
- Tests never call real X; fake it with respx.
- Outside input here: X replies, the archive zip, config and token files, the keep file, flags.
- Mutation: `uv run mutmut run`, then `uv run mutmut results`. Modules in `[tool.mutmut]` in
  `pyproject.toml`.
- Never commit a real X archive. Fixtures are small, redacted zips under `tests/fixtures/`.
- Run all checks: `uv run ruff format && uv run ruff check && uv run mypy && uv run pytest`.

## Git

- One spec per branch: `spec/NNN-slug`.
- Commit message references the spec id.
