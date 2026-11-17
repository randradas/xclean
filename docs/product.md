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

- Cover every kind of content or activity the user created on X (see Content types).
- Grow with X: when X adds a new kind of content, or its API opens a new one to removal,
  supporting it is a small, self-contained change.
- Select what to remove by rules: content type, date range, or everything. More rules can come
  later.
- Preview: show what matches before removing anything.
- Remove safely: track progress, respect X rate limits, and resume after an interruption with
  no double work.
- Show how a run is going. A cleanup can take hours or days because of rate limits, so the user
  can check at any time:
  - done, left, and failed counts, per content type
  - current state: working, or waiting on a rate limit and until when
  - estimated time to finish
  - a final report, listing failed items and why they failed

## Content types

Known today. Not all are removable through the X API; see `research/x-api.md` for which ones are.

Content the user made:

- Posts, including polls, threads, and posts with images or video
- Replies (comments)
- Quote posts
- Articles
- Community posts and replies
- Community Notes and note ratings
- Spaces hosted, and their recordings
- Drafts and scheduled posts
- Grok chats
- Profile fields: bio, avatar, header, location, website, pinned post

Activity the user did:

- Reposts (undo)
- Likes (undo)
- Bookmarks
- Follows, and followers (remove)
- Lists: owned, member of, followed
- Community memberships
- Mutes and blocks
- DMs
- Poll votes (probably not undoable)

## Sources

Finding content and removing it are separate. Removal is always by ID through the X API, and
costs X credits. Finding content can come from several sources, each added on its own:

1. X archive file: free, covers all posts and likes, takes 24 to 48 hours to arrive. First.
2. Later: timeline API (newest 3,200 posts, cheap), full-archive search (all posts, paid), and
   other list endpoints per content type.

## Access and deployment

- Bring your own app: each user creates their own X developer app, pays X API credits, and
  authorizes xclean to act as them (OAuth 2.0 user token). Owning the app also gets the cheaper
  owned-read rate.
- Local first: a CLI on the user's machine. Keys and archive stay local. Progress is saved, so a
  run can stop and resume any time.
- Cloud later: the same core runs as a scheduled job in the cloud, still with the user's own app.
  A shared hosted app for other users is out of scope for now.

## Non-goals

- Acting on any account other than the user's own.
- Editing or rewriting content.
- Scheduling or posting new content.

## Success measures

- After a run, nothing matching the user's rules is left on the account.
- Nothing outside the rules is removed.

## Open questions

- Order: which content types come first?
- Cost: the user pays X per request. Show estimated cost in the preview?
- Backup: export content before removing it?
