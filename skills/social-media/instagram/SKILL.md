---
name: instagram
description: "Publish images, reels, and carousels to an Instagram professional account via the official Graph API."
version: 1.0.0
author: KOPI AI AGENT
license: MIT
platforms: [linux, macos, windows]
metadata:
  kopi:
    tags: [instagram, social-media, publishing, reels, meta, graph-api]
    category: social-media
    homepage: https://developers.facebook.com/docs/instagram-platform/content-publishing
    related_skills: [xurl]
---

# Instagram Publishing

Publish content to an Instagram **professional** account (Business or
Creator) through Meta's official Graph API. No third-party MCP or SDK is
involved — a long-lived access token is too sensitive to hand to an
unaudited package, so this skill talks to `graph.facebook.com` directly
with a bundled stdlib-only script.

Use this skill when the user wants to post an image, a video/reel, or a
multi-image carousel to Instagram, check whether a post went out, or see
how much of the daily publishing quota is left.

## Hard platform limits (know these before promising anything)

- **Personal accounts cannot publish via API.** Meta requires a
  Business/Creator account linked to a Facebook Page.
- **Media must be a public URL.** Meta's servers download it; you cannot
  upload a local file directly. Host local files first — the
  `cloudflare-temporary-deploy` skill gives a public URL in seconds.
- **Video = Reel.** Feed-video uploads were retired by Meta; every video
  publishes as a reel (`media_type=REELS`). MP4 (H.264 + AAC), ≤ 15 min.
- **Images**: JPEG/PNG, carousel takes 2–10 items.
- **Quota**: ~50 API-published posts per rolling 24 h (`quota` shows usage).

## Setup (one-time, human does this)

1. Instagram account switched to **Professional** (Business or Creator),
   linked to a Facebook Page.
2. A Meta developer app with `instagram_basic`,
   `instagram_content_publish`, `pages_read_engagement` permissions.
3. A **long-lived** access token for that app/user, and the IG account id
   (`me/accounts` → page → `instagram_business_account`).
4. Store both in `~/.kopi/.env`:

```bash
INSTAGRAM_ACCESS_TOKEN=EAAG...      # long-lived token, ~60 days
INSTAGRAM_USER_ID=1784...           # IG professional-account id
# INSTAGRAM_GRAPH_API_VERSION=v23.0 # optional override
```

Verify wiring before any publish attempt:

```bash
python3 {skill_dir}/scripts/instagram_publish.py whoami
```

## Publishing (the script handles container + polling)

```bash
# image
python3 {skill_dir}/scripts/instagram_publish.py publish-image \
  "https://example.com/pic.jpg" --caption "New drop 🎉"

# video (published as a reel)
python3 {skill_dir}/scripts/instagram_publish.py publish-reel \
  "https://example.com/final.mp4" --caption "Behind the scenes"

# carousel (2–10 images)
python3 {skill_dir}/scripts/instagram_publish.py publish-carousel \
  "https://example.com/1.jpg" "https://example.com/2.jpg" --caption "Recap"
```

Each command creates the media container, polls until Meta finishes
processing (reels can take a minute or two), publishes, and prints the
`media_id` + `permalink` as JSON. A failed container prints Meta's error
verbatim — the usual causes are a URL that is not publicly reachable, an
unsupported codec, or an expired token.

### Prepared-but-unpublished mode

Add `--no-publish` to stop after processing: the script prints the ready
`container_id` and the exact `publish-container <id>` command for the
final step. Use this when the user wants to press the button themselves
(containers stay valid for 24 h):

```bash
python3 {skill_dir}/scripts/instagram_publish.py publish-reel "…" --no-publish
python3 {skill_dir}/scripts/instagram_publish.py publish-container 1790…
```

## Safety (MANDATORY)

- **Confirm before publishing.** Posting to a real account is public and
  outward-facing: show the user the media URL + caption and get an
  explicit yes before running a publish command (unless they already gave
  it in this conversation). When in doubt, use `--no-publish`.
- **Never** print, echo, or paste `INSTAGRAM_ACCESS_TOKEN` (or any part
  of `~/.kopi/.env`) into chat, logs, or command lines. The script reads
  it from the environment on its own.
- **Deleting is manual.** The API cannot delete published media; a wrong
  post must be removed in the Instagram app — one more reason to confirm
  first.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Graph API 400 … Invalid OAuth access token` | token expired (~60 days) — mint a new long-lived token |
| `Media download failed` / container `ERROR` | URL not publicly reachable (localhost, auth-gated, or blocked) |
| `The user is not an Instagram Business` | account is Personal — switch to Professional and re-link the Page |
| container stuck `IN_PROGRESS` past 10 min | Meta transcode backlog — `status <id>` later, container lives 24 h |
| `Application does not have permission` | app lacks `instagram_content_publish`, or token minted before the permission was added |
