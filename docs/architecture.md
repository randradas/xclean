# Architecture

Stack: Python 3.13 with uv. Typer and Rich (CLI), httpx (X API), SQLite (progress store),
keyring (tokens). Later cloud runner: AWS Lambda on a schedule.

## Components

- **Core**: rules, preview, progress store, removal loop. Knows nothing about how it is run.
- **Sources**: find content IDs (archive file first; timeline API, full-archive search later).
  One module per source.
- **Content types**: one module per type. Each says how to remove an item and its rate limits.
- **X client**: OAuth 2.0 user token, rate-limit handling (honors `x-rate-limit-*` headers).
- **Runners**: thin entry points over the core. CLI first; a cloud scheduled job later.

Adding a source or content type must not change the core.

## Data flow

1. A source reads content and writes items (type, ID, date, metadata) into the progress store,
   merging duplicates by ID.
2. Rules select items. Preview shows counts, estimated cost, and estimated time.
3. Removal loop takes pending items, calls the content type's remove, and records done or failed.
   Already gone counts as done. On rate limit, it waits until reset or exits to resume later.
4. Status reads the progress store at any time.

## Boundaries and constraints

- X API only; no scraping or browser automation (X developer guidelines).
- Rate limits and costs: `research/x-api.md`.
- Progress store must be portable: local file now, cloud storage later.
- Secrets stay with the user: local config now, a secrets store in the cloud later.
