# Product: xclean

Bulk-remove your own X content and activity, chosen by rules you set, with a preview first.

## Problem

X has no built-in way to clean up an account in bulk. A user who wants to wipe their history, or
drop everything older than some date, must delete posts and undo likes one by one by hand.

## Users

An X user cleaning up their own account. Example jobs:

- "Delete all my previous posts."
- "Delete my posts before a certain date."
- "Undo all my likes."
- "Remove my reposts and replies, keep my original posts."

## Goals

- Cover any content or activity the user created on X:
  - posts, including those with images or video
  - replies (comments)
  - quote posts
  - reposts (undo)
  - likes (undo)
- Select what to remove by rules: content type, date range, or everything. More rules can come
  later.
- Preview: show what matches before removing anything.
- Remove safely: track progress, respect X rate limits, and resume after an interruption with
  no double work.

## Non-goals

- Acting on any account other than the user's own.
- Editing or rewriting content.
- Scheduling or posting new content.

## Success measures

- After a run, nothing matching the user's rules is left on the account.
- Nothing outside the rules is removed.

## Open questions

- Data source: X API, the user's downloaded X archive, or both?
- Wider scope: do bookmarks, follows, lists, or DMs count as content to clean?
- Backup: export content before removing it?
