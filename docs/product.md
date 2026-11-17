# Product: xclean

Tool to clean up a user's X posts

## Problem

X has no built-in way to delete posts in bulk. A user who wants to wipe their history, or drop
everything older than some date, must delete posts one by one by hand.

## Users

An X user cleaning up their own account. Main jobs:

- "Delete all my previous posts."
- "Delete my posts before a certain date."

## Goals

- Delete all of the user's posts.
- Delete only posts older than a given date.
- Show what would be deleted before deleting anything (dry run).
- Survive interruption: a rerun picks up where it stopped, with no double work.

## Non-goals

- Acting on any account other than the user's own.
- Editing or rewriting posts.
- Scheduling or posting new content.

## Success measures

- After a run, no post matching the user's criteria is left on the account.
- No post outside the criteria is deleted.

## Open questions

- Data source: X API, the user's downloaded X archive, or both?
- Scope: do replies, reposts, and quote posts count as posts? Likes?
- Backup: export posts before deleting?
