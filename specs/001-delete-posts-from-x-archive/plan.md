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
- D16: Progress store is a local SQLite file in the user data folder, behind a small interface so
  the cloud runner can swap it.
- D17: Cost estimate uses a built-in price table with a "checked on" date; the preview shows it.

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
