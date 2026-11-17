---
status: draft
---

# Plan: Delete posts from X archive

Spec: `spec.md` (approved). Decision ids continue from the spec (last: D11).

## Approach

TODO: fill after grilling. Follows `docs/architecture.md` components.

## Decisions

Settled while grilling the plan. Newest last.

- D12: Python 3.13 with uv. Later cloud runner: AWS Lambda on a 15-minute schedule, one rate-limit
  window per invocation.
- D14: X app type "Native App": OAuth 2.0 with PKCE, no client secret, callback to a local
  address, `offline.access` for refresh tokens. Local callback support to be checked with a real
  app.
- D13: Plain HTTP with httpx. All X calls live in one small X client part (auth and refresh,
  rate-limit headers, retries). The rest of the code sees only simple results: deleted, already
  gone, rate limited, spending limit reached, failed.
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

## Changes

| Area / file | Change |
|---|---|
| TODO | TODO |

## Risks and mitigations

- Archive format is not documented by X. Field names for replies, quotes, reposts, the account
  id, and the archive date must be checked against a real archive.

## Test strategy

| AC | Check |
|---|---|
| AC1 | TODO |

## Open questions

- None yet.
