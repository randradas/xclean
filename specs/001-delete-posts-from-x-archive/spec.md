---
id: 001-delete-posts-from-x-archive
title: Delete posts from X archive
status: approved
created: 2026-11-17
---

# Delete posts from X archive

## Problem

An X user who wants to remove many of their own posts, all of them or those matching simple
rules, has no bulk way to do it. Deleting by hand takes days. The X API only lists the newest
3,200 posts, but the user's X archive lists all of them, for free. This first feature uses the
archive to find posts and the X API to delete them. Product decisions in `docs/product.md` apply
and are cited as `P<n>`.

## User stories

- As an X user, I want to delete all my posts so that my history is gone.
- As an X user, I want to delete only posts matching rules (date, type) so that I keep the rest.
- As an X user, I want to protect some posts so that no rule ever deletes them.
- As an X user, I want to see what will be deleted, and roughly what it costs and how long it
  takes, before anything is deleted.
- As an X user, I want to stop and resume a long run, and check its progress at any time.

## Acceptance criteria

Setup

- [ ] AC1: Given a user with their own X developer app, when they log in once through the
  browser, then later runs act as that user without logging in again, until they log out or
  revoke access. (D1; product "Access and deployment")
- [ ] AC2: Given an archive zip as X sends it, when the user points xclean at it, then posts are
  read without unzipping first. (P14)
- [ ] AC3: Given an archive from a different account than the logged-in one, when the user runs
  xclean, then it refuses and says why. Nothing is deleted. (D2)

Selecting posts

- [ ] AC4: Given no rules, when the user runs xclean, then every post (original, reply, quote) in
  the archive is selected. (P4)
- [ ] AC5: Given a type rule of original, reply, or quote, then only posts of that type are
  selected. A reply to the user's own post counts as a reply. (D3, P2, P4)
- [ ] AC6: Given a "before" or "after" date rule, then only posts strictly before or after that
  date, in the user's local time zone, are selected. (D5, P4, P17)
- [ ] AC7: Given several rules, then a post is selected only if it matches all of them. (D4)
- [ ] AC8: Given a keep list of post IDs or post links, one per line, then those posts are never
  selected, whatever the rules say. (D6, P5)
- [ ] AC9: Given reposts in the archive, then they are never selected. (D7, P2)
- [ ] AC27: Rules and the keep list are set as options on the command line. An invalid rule (bad
  date, unknown type) stops with a clear error and nothing runs. (D11)
- [ ] AC28: The preview states the rules it applied in plain words, e.g. "replies and quotes
  before 1 Jan 2020, keeping 3 posts". (D11)

Preview

- [ ] AC10: Given a selection, when the user runs xclean without the delete flag, then it shows a
  preview and deletes nothing. (P6)
- [ ] AC11: The preview shows: counts by type, oldest and newest post date, a few example posts,
  estimated cost marked as an estimate, and estimated time. (D8, P7)
- [ ] AC12: The preview can list every selected post on request. (D8)
- [ ] AC13: The preview shows the archive date and warns that newer posts are not covered. (P9)
- [ ] AC14: The preview flags the pinned post if it is selected. (P13)
- [ ] AC15: The preview shows how many reposts were skipped and that they are handled later. (D7)

Deleting

- [ ] AC16: Given the delete flag, when the user types the number of posts to delete, then
  deletion starts. Any other input cancels with nothing deleted. (P6)
- [ ] AC17: Given the delete flag and the yes flag, then deletion starts without typing. (P6)
- [ ] AC18: The selection is fixed when the user confirms. A run with different rules is a new
  run. A post already deleted, by xclean or by hand, is skipped and counted as done. (D9)
- [ ] AC19: Given a rate limit, the run waits until it resets, showing until when. (P10)
- [ ] AC20: Given Ctrl-C or any stop, when the user runs again, then it resumes where it stopped
  with no post deleted twice. (P10)
- [ ] AC21: Given a temporary error, the post is retried a few times, then marked failed with the
  reason. Failed posts can be retried later. (P11)
- [ ] AC22: Given X blocks requests because the spending limit is reached, the run stops cleanly,
  says why, and resumes after top-up. (P16)

Progress and report

- [ ] AC23: While running, the terminal shows a live progress line: done, left, failed, current
  state, estimated time left, and estimated spend so far. (P15, P16)
- [ ] AC24: A status command shows the same progress at any time, from another terminal or after
  a stop. (P15)
- [ ] AC25: At the end, a final report shows totals and lists failed posts with reasons. It is
  saved, and the status command shows it later. (D10, P11)

Docs

- [ ] AC26: User docs explain how to get the archive, create an X developer app, set a spending
  limit in the X Developer Console, and keep the archive as a backup. (P8, P16)

## Out of scope

- Reposts, likes, and any other content type (later specs).
- Finding posts through the X API (timeline, search).
- Posts newer than the archive.
- Rules beyond date and type (like count, words).
- A saved rules file (later, with the cloud runner, same rule names).
- Several accounts.
- Cloud runner.

## Decisions

Settled while grilling. Newest last.

- D1: A one-time browser login connects the user's X app. It is remembered until logout or
  revoke.
- D2: If the archive's account differs from the logged-in account, xclean refuses to run.
- D3: Type rule values: original, reply, quote. A reply to the user's own post is a reply.
- D4: Rules combine with AND.
- D5: Date rules are strict: "before 2020-01-01" excludes that day; "after" likewise.
- D6: Keep list takes post IDs or post links, one per line, in a plain text file.
- D7: Reposts in the archive are skipped; the preview shows how many and that they come later.
- D8: Preview shows counts by type, oldest and newest date, a few examples, and can list all.
- D9: A run's selection is fixed at confirm. New rules mean a new run. Already deleted posts are
  always skipped and counted as done.
- D10: Final report is shown at the end and saved; the status command shows it later.
- D11: Rules are set with command-line options in this spec; the preview echoes them in plain
  words. A rules file comes later.

## Open questions

- None.
