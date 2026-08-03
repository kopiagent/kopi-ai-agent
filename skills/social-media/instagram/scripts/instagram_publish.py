#!/usr/bin/env python3
"""Instagram content publishing via the official Instagram Graph API.

Stdlib only — no SDK, no third-party MCP. The publish flow is Meta's
two-step container protocol: create a media container, wait until the
server finishes processing it, then publish. Media must be hosted on a
PUBLICLY reachable URL (Meta's servers download it); local files must be
uploaded somewhere first.

Usage:
    python3 instagram_publish.py whoami
    python3 instagram_publish.py quota
    python3 instagram_publish.py publish-image <image_url> [--caption TEXT] [--no-publish]
    python3 instagram_publish.py publish-reel <video_url> [--caption TEXT] [--cover-url URL] [--no-publish]
    python3 instagram_publish.py publish-carousel <image_url>... [--caption TEXT] [--no-publish]
    python3 instagram_publish.py status <container_id>
    python3 instagram_publish.py publish-container <container_id>

Environment (from ~/.kopi/.env):
    INSTAGRAM_ACCESS_TOKEN          long-lived user/page token (required)
    INSTAGRAM_USER_ID               IG professional-account id (required)
    INSTAGRAM_GRAPH_API_VERSION     optional, default v23.0

`--no-publish` stops after the container is processed and prints the
container id — the "prepare everything, a human presses publish" mode.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_ROOT = "https://graph.facebook.com"

# Container processing is asynchronous server-side; reels regularly take
# a minute or two to transcode. Give up loudly rather than forever.
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 600

_FINISHED = "FINISHED"
_TERMINAL_FAILURES = ("ERROR", "EXPIRED")


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"missing {name} — set it in ~/.kopi/.env (see the skill's Setup section).",
            file=sys.stderr,
        )
        sys.exit(2)
    return value


def _api_version() -> str:
    return os.environ.get("INSTAGRAM_GRAPH_API_VERSION", "").strip() or "v23.0"


def _ssl_context():
    """Default SSL context, falling back to certifi's CA bundle — uv-managed
    Pythons often ship with no system CA store and fail every HTTPS call."""
    import ssl

    context = ssl.create_default_context()
    if context.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi

            context.load_verify_locations(cafile=certifi.where())
        except ImportError:
            pass
    return context


def _call(method: str, path: str, params: dict) -> dict:
    """One Graph API call. The token travels as a param (Graph convention)
    and is never printed — error output redacts the query string."""
    params = {k: v for k, v in params.items() if v is not None}
    params["access_token"] = _env("INSTAGRAM_ACCESS_TOKEN")
    query = urllib.parse.urlencode(params)
    url = f"{GRAPH_ROOT}/{_api_version()}/{path}"
    if method == "GET":
        request = urllib.request.Request(f"{url}?{query}")
    else:
        request = urllib.request.Request(url, data=query.encode(), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            message = json.loads(body).get("error", {}).get("message", body)
        except (json.JSONDecodeError, AttributeError):
            message = body
        print(f"Graph API {exc.code} on {path}: {message}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def _out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _wait_until_finished(container_id: str) -> None:
    """Poll the container until Meta finishes processing it."""
    deadline = time.time() + _POLL_TIMEOUT_S
    while True:
        status = _call("GET", container_id, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == _FINISHED:
            return
        if code in _TERMINAL_FAILURES:
            print(
                f"container {container_id} failed: {status.get('status', code)}",
                file=sys.stderr,
            )
            sys.exit(1)
        if time.time() >= deadline:
            print(
                f"container {container_id} still {code} after {_POLL_TIMEOUT_S}s; "
                "check `status` later or retry.",
                file=sys.stderr,
            )
            sys.exit(1)
        time.sleep(_POLL_INTERVAL_S)


def _publish_container(user_id: str, container_id: str) -> dict:
    published = _call("POST", f"{user_id}/media_publish", {"creation_id": container_id})
    media_id = published.get("id", "")
    details = _call("GET", media_id, {"fields": "permalink,media_type"}) if media_id else {}
    return {"media_id": media_id, **details}


def _create_and_maybe_publish(user_id: str, container: dict, publish: bool) -> dict:
    container_id = container.get("id", "")
    if not container_id:
        print(f"container creation returned no id: {container}", file=sys.stderr)
        sys.exit(1)
    _wait_until_finished(container_id)
    if not publish:
        return {
            "container_id": container_id,
            "status": _FINISHED,
            "next_step": (
                f"publish-container {container_id}  (or publish from the "
                "Instagram app — the container stays valid for 24h)"
            ),
        }
    return _publish_container(user_id, container_id)


def cmd_whoami(_args: argparse.Namespace) -> None:
    user_id = _env("INSTAGRAM_USER_ID")
    _out(
        _call(
            "GET",
            user_id,
            {"fields": "username,name,profile_picture_url,followers_count,media_count"},
        )
    )


def cmd_quota(_args: argparse.Namespace) -> None:
    user_id = _env("INSTAGRAM_USER_ID")
    _out(_call("GET", f"{user_id}/content_publishing_limit", {"fields": "quota_usage,config"}))


def cmd_status(args: argparse.Namespace) -> None:
    _out(_call("GET", args.container_id, {"fields": "status_code,status"}))


def cmd_publish_container(args: argparse.Namespace) -> None:
    user_id = _env("INSTAGRAM_USER_ID")
    _out(_publish_container(user_id, args.container_id))


def cmd_publish_image(args: argparse.Namespace) -> None:
    user_id = _env("INSTAGRAM_USER_ID")
    container = _call(
        "POST",
        f"{user_id}/media",
        {"image_url": args.image_url, "caption": args.caption},
    )
    _out(_create_and_maybe_publish(user_id, container, not args.no_publish))


def cmd_publish_reel(args: argparse.Namespace) -> None:
    user_id = _env("INSTAGRAM_USER_ID")
    container = _call(
        "POST",
        f"{user_id}/media",
        {
            "media_type": "REELS",  # feed video uploads were retired; video == reel
            "video_url": args.video_url,
            "caption": args.caption,
            "cover_url": args.cover_url,
            "share_to_feed": "true",
        },
    )
    _out(_create_and_maybe_publish(user_id, container, not args.no_publish))


def cmd_publish_carousel(args: argparse.Namespace) -> None:
    if not 2 <= len(args.image_urls) <= 10:
        print("carousel takes 2–10 image URLs.", file=sys.stderr)
        sys.exit(2)
    user_id = _env("INSTAGRAM_USER_ID")
    children = []
    for image_url in args.image_urls:
        child = _call(
            "POST",
            f"{user_id}/media",
            {"image_url": image_url, "is_carousel_item": "true"},
        )
        child_id = child.get("id", "")
        if not child_id:
            print(f"carousel item failed for {image_url}: {child}", file=sys.stderr)
            sys.exit(1)
        _wait_until_finished(child_id)
        children.append(child_id)
    container = _call(
        "POST",
        f"{user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": args.caption,
        },
    )
    _out(_create_and_maybe_publish(user_id, container, not args.no_publish))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    sub.add_parser("quota").set_defaults(fn=cmd_quota)

    p = sub.add_parser("status")
    p.add_argument("container_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("publish-container")
    p.add_argument("container_id")
    p.set_defaults(fn=cmd_publish_container)

    p = sub.add_parser("publish-image")
    p.add_argument("image_url")
    p.add_argument("--caption", default=None)
    p.add_argument("--no-publish", action="store_true")
    p.set_defaults(fn=cmd_publish_image)

    p = sub.add_parser("publish-reel")
    p.add_argument("video_url")
    p.add_argument("--caption", default=None)
    p.add_argument("--cover-url", default=None)
    p.add_argument("--no-publish", action="store_true")
    p.set_defaults(fn=cmd_publish_reel)

    p = sub.add_parser("publish-carousel")
    p.add_argument("image_urls", nargs="+")
    p.add_argument("--caption", default=None)
    p.add_argument("--no-publish", action="store_true")
    p.set_defaults(fn=cmd_publish_carousel)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
