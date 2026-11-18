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

- [x] T7: Store interface and SQLite store: create run with frozen selection, item statuses,
  one-run lock. (AC18, AC20)
- [x] T8: Store: save and load final report with failures and reasons. (AC25)
- [x] T9: Price table with checked-on date; cost and time estimates. (AC11)

X client and login

- [x] T10: X client results: deleted, already gone, rate limited with reset time, spending limit
  reached, temporary error, failed (respx). (AC18, AC19, AC21, AC22)
- [x] T11: Token store (keyring, fallback file readable only by user, one-time warning) and token
  refresh on expiry. (AC1)
- [x] T12: PKCE login with local callback and paste-URL fallback; `login` and `logout` commands.
  (AC1)
- [x] T13: Posts content type: remove by ID through the X client. (AC18)

Engine

- [x] T14: Removal loop: one at a time, record each result before the next request, already gone
  counts as done, retries then failed. (AC18, AC21)
- [x] T15: Rate-limit wait until reset (fake clock); spending limit stops cleanly. (AC19, AC22)
- [x] T16: Stop and resume deletes each post exactly once; retry-failed requeues failed items.
  (AC20, AC21)

Archive (needs the real archive)

- [ ] T17: Inspect the real archive; record field names for type, account ID, archive date in
  `docs/research/`; build redacted fixture zips. (AC2, AC9)
- [ ] T18: Archive source: read zip in place, account ID, archive date, posts classified as
  original, reply, quote, repost. (AC2, AC9, AC13)
- [ ] T19: Account guard against logged-in user; fetch pinned post ID. (AC3, AC14)

CLI

- [ ] T20: Preview: counts by type, date range, examples, rules in words, archive date warning,
  pinned flag, skipped reposts, cost and time; small runs must not read as zero time (review 1).
  (AC11, AC13, AC14, AC15)
- [ ] T21: `posts` command preview and `--list`; prove zero delete calls without `--delete`.
  (AC10, AC12, AC27)
- [ ] T22: `--delete` with typed count confirm or `--yes`; unfinished run asks resume or drop;
  take the run lock (D22) around every run (review 1).
  (AC16, AC17, AC18)
- [ ] T23: Live progress line: done, left, failed, state, time left, spend so far. (AC23)
- [ ] T24: `status`, `resume`, `retry-failed` commands; status shows saved report. (AC20, AC21,
  AC24, AC25)

Docs and release

- [ ] T25: README user docs: get archive, create X app, set spending limit, keep archive,
  commands. (AC26)
- [ ] T26: `docs/release-checklist.md`; run it on the real account starting with one test post;
  confirm local callback and delete price, update price table; check whether already-gone and
  failed deletes are billed (review 1). (AC1, AC11)

## Review

Filled by `/review` after each task group. Open R tasks come before the next T task.

### Review 1: T1-T16 (6ce922e..b5b93dd), closed at e3ea121

- [x] R1: Malformed X error body (`errors` not a list of objects) crashes the run on every
  resume. (bugs)
- [x] R2: Non-JSON body from the token endpoint crashes the run; treat as temporary. (bugs)
- [x] R3: 429 on token refresh reports "login expired"; treat as temporary. (bugs)
- [x] R4: Token save failure after refresh loses the rotated refresh token; write atomically,
  and `logout` survives a broken token file. (bugs)
- [x] R5: Local clock ahead of X turns rate-limit waits into ~1 s retries; set a minimum wait,
  one shared default wait. (bugs; AC19)
- [x] R6: Resume ignores a stored future `wait_until`. (bugs; AC19, AC20)
- [x] R7: `me()` crashes with KeyError when the reply has no `data`. (bugs)
- [x] R8: `config.save` writes broken TOML when a value contains `"`. (bugs)
- [x] R9: Store database and lock file readable by other users; make them owner-only. (bugs)
- [x] R10: 403 when credits run out marks posts failed and continues; one 403 fails that post,
  three in a row stop the run with X's message. (spec; AC22)
- [x] R11: `retry-failed` keeps the old run message. (spec; AC21)
- [x] R12: Duplicate post IDs in a selection crash the run start; drop duplicates. (spec; AC18)
- [x] R13: Token exchange, refresh and revoke send HTTP outside the X client; move them in.
  Callback server stays in `auth.py` (D14). (standards; D13)
- [x] R14: Move `MemoryTokenStore` test double out of production code. (standards)
- ~~R15: Rename `Remover` to the glossary term, content type.~~ skipped: `ContentType` is
  already the enum in `model.py`; `Remover` says what it does.
- ~~R16: Run lock not taken by the engine.~~ moved to T22.
- ~~R17: Time estimate is zero for small runs.~~ moved to T20.
- ~~R18: Billing of already-gone and failed deletes is a guess.~~ moved to T26.
- ~~R19: `x-rate-limit-remaining` ignored on success.~~ skipped: one 429 per window is fine.
- ~~R20: Unrequested extras (empty date range check, `#` in keep file, NOT_LOGGED_IN result,
  redirect config, `--version`).~~ skipped: all reasonable.
- ~~R21: Other smells (paired params, string price key and ids, `estimate_duration` placement,
  generic `_removal_result`, unused `RateLimit.daily`, Ending vs Outcome, engine imports
  `xclient`).~~ skipped: judgement calls, not worth the churn.
- ~~R22: No `tests/fixtures/` folder.~~ skipped: T17 creates it.
- ~~R25: Approved `plan.md` edited without asking (607c6b2 changes table, cf1cfe8 risks).~~
  kept: user approved both on 2026-11-18; they match the code and change no decision.
- [x] R23: Token reply with a bad `expires_in` (null, text) crashes the run; keep the tokens
  (X already rotated them) and assume 2 hours. (bugs; from R2 check)
- [x] R24: The 403 counter resets only on success, so 403s with other answers between them
  still stop the run; reset on any other answer. (bugs; from R10 check)

### Review 2: mutation trial on `engine.py` (at 9ee4b96), closed at d0d61f8

- [x] R26: Spending limit and not logged in return the right ending, but no test checks the run
  is saved STOPPED with X's message. (mutation; AC22)
- [x] R27: No test checks the stored `wait_until` and message while a resumed run waits out an
  old rate limit, or during a rate-limit wait in the loop. (mutation; AC19, AC20)
- [x] R28: No test proves the 403 counter resets to zero after a success or a run-out retry
  (refuse, refuse, other, refuse, refuse goes on). (mutation; AC22)
- [x] R29: `set_state` and other run updates silently change nothing for an unknown run id;
  raise instead. (mutation)
- [x] R30: Stored messages ("interrupted", "rate limit", the 403 reason) are not asserted.
  (mutation)
- ~~R31: `RealClock` has no tests.~~ skipped: thin wrapper over the system clock.
- ~~R32: `rate_limited` count mutants and `>=` at `engine.py:71` survive.~~ skipped: equivalent,
  same behaviour.
