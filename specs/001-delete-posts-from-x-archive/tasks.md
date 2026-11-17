# Tasks: Delete posts from X archive

Order matters. Each task: small, testable, names the acceptance criteria it covers.
Tests first in every task. T17 needs the author's real X archive; tasks before it do not.

Foundation

- [x] T1: Scaffold package: `pyproject.toml` with uv, `xclean` script, ruff, mypy strict, pytest,
  respx; CI on Ubuntu and macOS; fill stack and test command in `CLAUDE.md`,
  `docs/architecture.md`, `docs/conventions.md`. (setup for all AC)
- [x] T2: Model (item, content type, status, run) and XDG paths honoring `XDG_*`. (AC1, AC24)

Rules and keep list

- [x] T3: Parse and validate rules: type, before, after; clear errors for bad values. (AC5, AC6,
  AC27)
- [x] T4: Select items: no rules selects all posts, rules AND together, reposts never match.
  (AC4, AC7, AC9)
- [x] T5: Describe applied rules in plain words. (AC28)
- [x] T6: Parse keep file (IDs and post links, one per line); kept posts never selected. (AC8)

Store and estimates

- [ ] T7: Store interface and SQLite store: create run with frozen selection, item statuses,
  one-run lock. (AC18, AC20)
- [ ] T8: Store: save and load final report with failures and reasons. (AC25)
- [ ] T9: Price table with checked-on date; cost and time estimates. (AC11)

X client and login

- [ ] T10: X client results: deleted, already gone, rate limited with reset time, spending limit
  reached, temporary error, failed (respx). (AC18, AC19, AC21, AC22)
- [ ] T11: Token store (keyring, fallback file readable only by user, one-time warning) and token
  refresh on expiry. (AC1)
- [ ] T12: PKCE login with local callback and paste-URL fallback; `login` and `logout` commands.
  (AC1)
- [ ] T13: Posts content type: remove by ID through the X client. (AC18)

Engine

- [ ] T14: Removal loop: one at a time, record each result before the next request, already gone
  counts as done, retries then failed. (AC18, AC21)
- [ ] T15: Rate-limit wait until reset (fake clock); spending limit stops cleanly. (AC19, AC22)
- [ ] T16: Stop and resume deletes each post exactly once; retry-failed requeues failed items.
  (AC20, AC21)

Archive (needs the real archive)

- [ ] T17: Inspect the real archive; record field names for type, account ID, archive date in
  `docs/research/`; build redacted fixture zips. (AC2, AC9)
- [ ] T18: Archive source: read zip in place, account ID, archive date, posts classified as
  original, reply, quote, repost. (AC2, AC9, AC13)
- [ ] T19: Account guard against logged-in user; fetch pinned post ID. (AC3, AC14)

CLI

- [ ] T20: Preview: counts by type, date range, examples, rules in words, archive date warning,
  pinned flag, skipped reposts, cost and time. (AC11, AC13, AC14, AC15)
- [ ] T21: `posts` command preview and `--list`; prove zero delete calls without `--delete`.
  (AC10, AC12, AC27)
- [ ] T22: `--delete` with typed count confirm or `--yes`; unfinished run asks resume or drop.
  (AC16, AC17, AC18)
- [ ] T23: Live progress line: done, left, failed, state, time left, spend so far. (AC23)
- [ ] T24: `status`, `resume`, `retry-failed` commands; status shows saved report. (AC20, AC21,
  AC24, AC25)

Docs and release

- [ ] T25: README user docs: get archive, create X app, set spending limit, keep archive,
  commands. (AC26)
- [ ] T26: `docs/release-checklist.md`; run it on the real account starting with one test post;
  confirm local callback and delete price, update price table. (AC1, AC11)
