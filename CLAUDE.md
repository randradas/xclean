# xclean

Bulk-remove your own X content and activity, chosen by rules you set, with a preview first.

Stack: Python 3.13, uv, Typer, Rich, httpx, SQLite. macOS and Linux.
Check: `uv run ruff format && uv run ruff check && uv run mypy && uv run pytest`

## How we work

Spec driven. No code without an approved spec.
Flow: `/spec` -> `/plan` -> `/tasks` -> `/implement` (with `/review` after each task group).
Details: `specs/README.md`.

## Where to look (read only what the task needs)

| Need | Read |
|---|---|
| Why the product exists, users, goals | `docs/product.md` |
| System shape, modules, data flow | `docs/architecture.md` |
| Code style, testing, commits | `docs/conventions.md` |
| What to test and how | `docs/testing.md` |
| Domain terms | `docs/glossary.md` |
| Past decisions | `docs/decisions/` |
| Current feature work | `specs/NNN-*/` |

Full doc index: `docs/README.md`.

## Hard rules

- Do not change a spec marked `status: approved` without asking.
- Tick tasks in `tasks.md` as you finish them.
- Write an ADR in `docs/decisions/` only for decisions that are hard to reverse, surprising, and a real trade-off.
