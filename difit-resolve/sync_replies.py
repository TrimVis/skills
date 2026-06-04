#!/usr/bin/env python3
"""Append Claude replies into a running difit instance's thread state.

Usage:
    python3 sync_replies.py --port <PORT> --replies <REPLIES_JSON>

REPLIES_JSON file format (a list of reply objects):

    [
        {
            "filePath": "src/foo.ts",
            "position": {"side": "new", "line": 42},
            "body": "**applied** - what changed in one line"
        },
        {
            "filePath": "src/bar.ts",
            "position": {"side": "new", "line": {"start": 12, "end": 18}},
            "body": "**skipped** - reason"
        }
    ]

position.line: int for single-line, {"start": int, "end": int} for range.
The body convention is markdown; the first **<status>** tag is parsed back
when /difit-resolve reads the reply on a future run.

Important gotchas (verified against difit 5.0.1):
- The POST URL is /api/comments WITHOUT base/target query params. Passing
  short SHAs as query params spawns a NEW empty session and your write
  silently lands nowhere -- the server still returns {"success":true}.
- This script does a GET-modify-POST: it pulls current state, appends to
  matching threads' messages, then posts the whole state back. So it's
  idempotent against an already-applied set (same body skipped), but it
  WILL overwrite any concurrent UI edits made between the GET and POST.

Exit codes:
  0 - all replies appended (or already present)
  1 - difit unreachable, or POST failed
  2 - one or more replies had no matching thread on the server (printed)
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def nanoid() -> str:
    return "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))


def position_key(pos: dict) -> tuple:
    side = pos.get("side", "new")
    line = pos["line"]
    if isinstance(line, dict):
        return (side, "range", line["start"], line["end"])
    return (side, "single", line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--replies", required=True, help="Path to replies JSON")
    ap.add_argument("--author", default="Claude", help="Author label for the replies")
    args = ap.parse_args()

    try:
        state = json.loads(subprocess.check_output(
            ["difit", "comment", "get", "--port", str(args.port), "--format", "json"],
            stderr=subprocess.PIPE,
        ))
    except subprocess.CalledProcessError as exc:
        print(f"difit unreachable on port {args.port}: {exc.stderr.decode()}", file=sys.stderr)
        return 1

    with open(args.replies) as f:
        replies = json.load(f)

    idx = {(t["filePath"], position_key(t["position"])): t for t in state["threads"]}
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    appended = 0
    missing: list[tuple] = []
    for r in replies:
        key = (r["filePath"], position_key(r["position"]))
        thread = idx.get(key)
        if thread is None:
            missing.append(key)
            continue
        existing_bodies = {m["body"] for m in thread["messages"]}
        if r["body"] in existing_bodies:
            continue
        thread["messages"].append({
            "id": nanoid(),
            "body": r["body"],
            "author": args.author,
            "createdAt": now,
            "updatedAt": now,
        })
        thread["updatedAt"] = now
        appended += 1

    # POST without base/target query params -- see module docstring.
    url = f"http://localhost:{args.port}/api/comments"
    req = urllib.request.Request(
        url,
        data=json.dumps(state).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": f"http://localhost:{args.port}",
            "Referer": f"http://localhost:{args.port}/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            if resp.status != 200 or '"success":true' not in body:
                print(f"POST failed: HTTP {resp.status} {body[:200]}", file=sys.stderr)
                return 1
    except urllib.error.URLError as exc:
        print(f"POST failed: {exc}", file=sys.stderr)
        return 1

    print(f"appended {appended} reply/replies (of {len(replies)} requested)")
    if missing:
        for fp, key in missing:
            print(f"WARN no thread on server for {fp} {key}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
