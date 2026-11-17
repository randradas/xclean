# Research: X API for cleanup

Checked 2026-11-17 against docs.x.com. X changes pricing and limits often; recheck before relying
on numbers.

## Access and pricing

- No free tier for new developers. Default plan is pay-per-use: buy credits, each request costs.
- Relevant rates ([pricing](https://docs.x.com/x-api/getting-started/pricing)):
  - Owned reads (own posts, bookmarks, following, lists, ...): $0.001 per resource, only when the
    authenticated user also owns the app.
  - "Interaction: delete": $0.010 per request.
  - "Content manage": $0.005 per request.
  - Likes, mutes, blocks reads: $0.001 per resource.
- Unverified: which billing category post delete, unlike, and unrepost fall under. Check the
  Developer Console.
- Out of credits or over the spending limit: HTTP 402 with problem type
  `https://api.x.com/2/problems/credits-depleted` (reported by developers, not in X's docs).
  Some report a 403 instead when the balance is negative or the app is not enrolled.
- Same resource is not charged twice within one UTC day (soft guarantee).
- Implication: each user brings their own X developer app and credits. Cleanup costs money,
  roughly $0.005 to $0.010 per item removed, so the preview should show an estimated cost.

## Finding the user's content

- `GET /2/users/:id/tweets` returns only the 3,200 most recent posts (800 with
  `exclude=replies`). Past that it returns success with no data. It includes replies, quotes,
  and reposts, typed via `referenced_tweets`.
- So the API alone cannot find old posts on a big account. The user's X data archive can:
  `tweets.js` lists all posts, `like.js` all likes. Delete-by-ID through the API works for any
  ID, wherever it came from.
- Full-archive search (`GET /2/tweets/search/all`, `from:<user>`) is available on pay-per-use
  and covers posts back to 2006, up to 500 per request
  ([search intro](https://docs.x.com/x-api/posts/search/introduction.md)). It is billed as post
  reads (likely $0.005 each, not the owned-read rate; unverified). It does not find likes.
- Conclusion: three ways to find posts (timeline, full-archive search, archive file), one way to
  remove (delete by ID).

## Removable content types

Per-user rate limits from [rate limits](https://docs.x.com/x-api/fundamentals/rate-limits.md).
Throughput is the ceiling if the limit is the only constraint.

| Content type | Find | Remove | Limit | Max per day |
|---|---|---|---|---|
| Posts, replies, quotes, media posts | timeline (3,200) or archive | `DELETE /2/tweets/:id` | 50/15min | ~4,800 |
| Reposts | timeline or archive | `DELETE /2/users/:id/retweets/:tweet_id` | 50/15min | ~4,800 |
| Likes | `GET liked_tweets` (75/15min) or archive | `DELETE /2/users/:id/likes/:tweet_id` | 50/15min, 1,000/24h | 1,000 |
| Bookmarks | `GET bookmarks` | `DELETE /2/users/:id/bookmarks/:tweet_id` | 50/15min | ~4,800 |
| Follows | `GET following` | `DELETE .../following/:target_user_id` | 50/15min | ~4,800 |
| Mutes | `GET muting` | `DELETE .../muting/:target_user_id` | 50/15min | ~4,800 |
| Blocks | `GET blocking` | `DELETE .../blocking/:target_user_id` | not listed | ? |
| Owned lists | `GET owned_lists` | `DELETE /2/lists/:id` | 300/15min | many |
| Followed lists | `GET followed_lists` | `DELETE .../followed_lists/:list_id` | 50/15min | ~4,800 |
| Lists the user is on | `GET list_memberships` | only the list owner can remove | - | no |
| DMs (legacy) | `GET /2/dm_events` (15/15min) | `DELETE /2/dm_events/:id` | 300/15min, 1,500/24h | 1,500 |
| Community Notes written | search notes written | delete a community note | not checked | ? |

Example: 20,000 likes take at least 20 days. 10,000 posts take about 2 days.

## Not removable through the API (today)

- Followers (no "remove follower" endpoint; block then unblock is a known workaround, side
  effects).
- Community memberships (no leave endpoint).
- Articles (create and publish only).
- Drafts and scheduled posts (no endpoints).
- Profile fields (read only).
- Grok chats, Spaces and recordings, Community Note ratings, poll votes: no endpoints found.
- X Chat encrypted DMs: separate API; no listing or delete endpoint documented.

## Policy risks

[Developer guidelines](https://docs.x.com/developer-guidelines.md) ban bulk or automated *liking*
and *following*, scraping, browser automation, and getting around rate limits. They say nothing
about bulk *deleting* or *unliking* your own content. Not a clear ban, but stay strictly inside
rate limits, act only on the user's explicit selection, and recheck the guidelines.
