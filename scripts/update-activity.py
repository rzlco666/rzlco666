#!/usr/bin/env python3
"""Regenerate the "Recent GitHub Activity" section of README.md.

Reads the user's public GitHub events (merged/opened PRs and published
releases), keeps the 5 most recent, and rewrites the content between the
<!--START_SECTION:activity--> and <!--END_SECTION:activity--> markers.

Auth: GITHUB_TOKEN env var (in GitHub Actions this is the built-in token,
no extra secret needed). Without a token the unauthenticated rate limit
(60 requests/hour) applies — enough for a manual test run.

Usage: python3 scripts/update-activity.py   (run from the repo root)
Exit 0 when the file was updated or was already up to date; exit 1 on
error (no events found, markers missing, API failure).
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

USERNAME = "rzlco666"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(REPO_ROOT, "README.md")
START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"
MAX_ITEMS = 5


def fetch_events(token):
    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=30"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "rzlco666-profile-activity",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fmt_date(iso):
    # "2026-11-06T03:09:16Z" -> "6 Nov 2026"
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    return f"{dt.day} {dt.strftime('%b %Y')}"


def build_items(events):
    """Newest-first events -> up to MAX_ITEMS display lines.

    A PR that was both opened and merged shows once, as merged.
    """
    seen_prs = set()
    items = []
    for ev in events:
        etype = ev.get("type")
        payload = ev.get("payload", {})
        repo = ev.get("repo", {}).get("name", "")
        created = ev.get("created_at", "")
        if etype == "PullRequestEvent":
            pr = payload.get("pull_request") or {}
            action = payload.get("action")
            if action == "closed" and pr.get("merged"):
                action = "merged"
            if action not in ("merged", "opened"):
                continue
            number = pr.get("number")
            key = (repo, number)
            if key in seen_prs:
                continue
            seen_prs.add(key)
            emoji = "🎉" if action == "merged" else "💪"
            verb = "Merged PR" if action == "merged" else "Opened PR"
            url = pr.get("html_url") or f"https://github.com/{repo}/pull/{number}"
            items.append(
                f"{emoji} {verb} [#{number}]({url}) in "
                f"[{repo}](https://github.com/{repo}) — {fmt_date(created)}"
            )
        elif etype == "ReleaseEvent" and payload.get("action") == "published":
            rel = payload.get("release") or {}
            tag = rel.get("tag_name", "")
            url = rel.get("html_url") or f"https://github.com/{repo}/releases"
            items.append(
                f"🚀 Published release [{tag}]({url}) in "
                f"[{repo}](https://github.com/{repo}) — {fmt_date(created)}"
            )
        if len(items) >= MAX_ITEMS:
            break
    return items


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        events = fetch_events(token)
    except Exception as exc:  # noqa: BLE001 - surface any API failure plainly
        print(f"failed to fetch GitHub events: {exc}", file=sys.stderr)
        return 1
    items = build_items(events)
    if not items:
        print("no activity items found; leaving README unchanged", file=sys.stderr)
        return 1
    lines = [f"{i}. {text}" for i, text in enumerate(items, 1)]
    new_block = START + "\n" + "\n".join(lines) + "\n" + END
    with open(README, encoding="utf-8") as f:
        content = f.read()
    if START not in content or END not in content:
        print("activity markers not found in README.md", file=sys.stderr)
        return 1
    before = content.split(START)[0]
    after = content.split(END, 1)[1]
    new_content = before + new_block + after
    if new_content == content:
        print("activity already up to date")
        return 0
    with open(README, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"updated activity: {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
