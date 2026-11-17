---
status: draft
---

# Plan: Delete posts from X archive

Spec: `spec.md` (approved). Decision ids continue from the spec (last: D11).

## Approach

Follows `docs/architecture.md`: a core that knows nothing about how it runs, with sources,
content types, an X client, and a CLI runner around it.

1. **Login** (`xclean login`): OAuth 2.0 PKCE in the browser, callback to a local address, tokens
   saved via the token store (D14, D15). The X client refreshes tokens on its own.
2. **Read** (`xclean posts --archive x.zip ...`): the archive source opens the zip in place, reads
   the account ID, the archive date, and every post, and classifies each as original, reply,
   quote, or repost (P14, AC2, AC9).
3. **Guard**: the X client fetches the logged-in user (ID, pinned post). Different account from
   the archive: stop (AC3).
4. **Select**: rules (type, before, after; AND) and the keep list pick items. Reposts never match
   (AC4 to AC9, AC27).
5. **Preview**: counts by type, date range, examples, rules in plain words, archive date warning,
   pinned post flag, skipped reposts, estimated cost (price table, D17) and time (rate limit).
   `--list` prints all. Nothing else happens without `--delete` (AC10 to AC15, AC28).
6. **Start run** (`--delete`): confirm by typed count or `--yes`. The selection is frozen into the
   progress store as a run with pending items. A lock allows one run per account (D22, AC16 to
   AC18).
7. **Removal loop** (core): take pending items one at a time (D23), call the posts content type's
   remove, record the result. Already gone counts as done. Rate limited: wait until reset with a
   live countdown. Spending limit: stop cleanly. Temporary error: retry a few times with backoff,
   then mark failed (AC19 to AC22).
8. **Progress**: the live line reads from the store after each item; `xclean status` reads the
   same store from anywhere; the final report is saved to the store (AC23 to AC25).
9. **Resume** (`xclean resume`, `xclean retry-failed`): reopen the current run; Ctrl-C at any time
   is safe because each result is written before the next request (AC20, AC21).

## Decisions

Settled while grilling the plan. Newest last.

- D12: Python 3.13 with uv. Later cloud runner: AWS Lambda on a 15-minute schedule, one rate-limit
  window per invocation.
- D13: Plain HTTP with httpx. All X calls live in one small X client part (auth and refresh,
  rate-limit headers, retries). The rest of the code sees only simple results: deleted, already
  gone, rate limited, spending limit reached, failed.
- D14: X app type "Native App": OAuth 2.0 with PKCE, no client secret, callback to a local
  address, `offline.access` for refresh tokens. Local callback support to be checked with a real
  app.
- D15: Tokens go in the OS keyring (macOS Keychain, Linux Secret Service). With no keyring, they
  go in a file readable only by the user, with a one-time warning.
- D16: Progress store is a local SQLite file in the user data folder, behind a small interface so
  the cloud runner can swap it.
- D17: Cost estimate uses a built-in price table with a "checked on" date; the preview shows it.
- D18: macOS and Linux supported, tested in CI on both. Windows not promised.
- D19: XDG folders on macOS and Linux, honoring `XDG_*` variables. Config `~/.config/xclean/`
  (client ID, settings). Data `~/.local/share/xclean/` (progress store, reports, fallback token
  file). State `~/.local/state/xclean/` (logs). Never put tokens in config: it is often kept in
  a dotfiles repo.
- D20: Typer for commands, Rich for live progress, tables, and prompts.
- D21: Commands: `login`, `logout`, `posts` (preview; `--delete [--yes]` starts a run),
  `resume`, `retry-failed`, `status`.
- D22: One run per account at a time, enforced by a lock. Starting a new run while one is
  unfinished asks to resume or drop it first.
- D23: One request at a time, pacing only by X rate-limit headers.
- D24: ruff (lint, format), mypy strict, pytest, respx for faking X. CI on GitHub Actions,
  Ubuntu and macOS.
- D25: Automated tests never call real X. A manual release checklist runs against the author's
  real account, starting with one test post.
- D26: Install with `uv tool install git+https://github.com/randradas/xclean`. PyPI later.

## Changes

| Area / file | Change |
|---|---|
| `pyproject.toml`, `uv.lock` | New package `xclean`, script `xclean`, deps, ruff and mypy config |
| `src/xclean/model.py` | Item, content type, item status, run |
| `src/xclean/paths.py` | XDG folder resolution |
| `src/xclean/config.py` | Client ID and settings in config folder |
| `src/xclean/auth.py` | PKCE login flow, local callback, token store (keyring, fallback file) |
| `src/xclean/xclient.py` | httpx client: auth header, refresh, rate-limit headers, retries, simple results |
| `src/xclean/sources/archive.py` | Read zip: account ID, archive date, posts with type |
| `src/xclean/content_types/posts.py` | Remove a post by ID; its rate limit and price key |
| `src/xclean/rules.py` | Parse and validate rules, select items, describe rules in words |
| `src/xclean/keep.py` | Parse keep file: IDs or post links |
| `src/xclean/store.py` | Store interface, SQLite store: runs, items, results, lock, report |
| `src/xclean/prices.py` | Price table with checked-on date |
| `src/xclean/preview.py` | Counts, examples, warnings, cost and time estimates |
| `src/xclean/engine.py` | Removal loop: waits, retries, stops, resume |
| `src/xclean/cli.py` | Typer runner: all commands, confirm prompt, live progress, status, report |
| `tests/` | Unit tests per module, fake archive zips, respx fakes for X |
| `.github/workflows/ci.yml` | ruff, mypy, pytest on Ubuntu and macOS |
| `README.md` | User docs: archive, X app setup, spending limit, keep archive, commands |
| `docs/release-checklist.md` | Manual real-account checks (D25) |
| `CLAUDE.md`, `docs/architecture.md`, `docs/conventions.md` | Fill stack, tooling, test command |

## Risks and mitigations

- **Archive format not documented by X.** Field names for replies, quotes, reposts, the account
  ID, and the archive date must be checked against a real archive. Mitigation: build fixtures
  from the author's real archive (redacted) before writing the parser; parse defensively and
  report unknown records instead of guessing.
- **Quote posts may be hard to detect in the archive.** Mitigation: same as above; if no reliable
  signal exists, raise it as a spec change rather than guess.
- **Local callback may be rejected by X app settings.** Mitigation: check with a real app first
  (D14). Fallback: user pastes the redirect URL back into the terminal.
- **Price category for post delete unknown.** Mitigation: price table assumes the higher known
  delete price until checked with one real delete (D17, D25).
- **X changes limits, prices, or endpoints.** Mitigation: all X knowledge sits in the X client,
  the posts content type, and the price table; preview shows the price date.
- **Deleting is irreversible.** Mitigation: preview by default, typed confirmation, keep list,
  account guard, and tests that prove no request is sent without `--delete`.

## Test strategy

| AC | Check |
|---|---|
| AC1 | Unit: PKCE URL and token exchange with respx; tokens saved and reloaded; refresh on 401. Manual: real login. |
| AC2 | Unit: archive source reads a fixture zip without extracting to disk. |
| AC3 | Unit: archive account differs from fake `/users/me` -> error, zero delete calls. |
| AC4 | Unit: no rules selects all originals, replies, quotes. |
| AC5 | Unit: each type rule; self-reply counts as reply. |
| AC6 | Unit: strict before and after at the boundary, in a fixed local time zone. |
| AC7 | Unit: combined rules select only the intersection. |
| AC8 | Unit: keep file with IDs and links; kept posts never selected. |
| AC9 | Unit: reposts never selected under any rules. |
| AC10 | CLI test: preview run makes zero delete calls. |
| AC11 | CLI test: preview output has counts, dates, examples, cost marked estimate, time. |
| AC12 | CLI test: `--list` prints every selected post. |
| AC13 | CLI test: archive date and newer-posts warning shown. |
| AC14 | CLI test: pinned post flagged when selected, not when kept. |
| AC15 | CLI test: skipped repost count shown. |
| AC16 | CLI test: correct typed count starts; wrong input cancels with zero delete calls. |
| AC17 | CLI test: `--yes` starts without prompt. |
| AC18 | Engine test: selection frozen at start; 404 counted as done. |
| AC19 | Engine test: 429 with reset header waits until reset (fake clock). |
| AC20 | Engine test: stop mid-run, resume, each post deleted exactly once. |
| AC21 | Engine test: 5xx retried, then failed with reason; `retry-failed` requeues. |
| AC22 | Engine test: spending-limit error stops cleanly; resume continues. |
| AC23 | CLI test: progress line fields present. |
| AC24 | CLI test: `status` from a separate process reads the store. |
| AC25 | Engine and CLI test: report saved with failures and reasons; `status` shows it. |
| AC26 | Review: README covers archive, app setup, spending limit, keep archive. |
| AC27 | CLI test: bad date or type errors out, zero calls. |
| AC28 | Unit: rules described in plain words. |

## Open questions

- Archive field names (see Risks): answered when the author's archive arrives.
