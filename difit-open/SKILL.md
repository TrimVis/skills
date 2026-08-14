---
name: difit-open
description: Open a REVIEW.md (written by /difit-review) in difit's browser UI for interactive review. Starts a difit instance (or pushes to one the user already has running on a given port), populates it with the unresolved threads from REVIEW.md. Optional — REVIEW.md is the source of truth; this skill just provides a nicer way to add reply comments than editing the file directly.
user-invocable: true
---

# Difit Open Skill

Spin difit on the diff `/difit-review` analysed, push the unresolved threads from `REVIEW.md` into it, hand the user the URL. The user reviews and adds replies in the browser; `/difit-resolve` later pulls those replies back out and merges them into `REVIEW.md`.

## Arguments

- `name` (optional, positional): which review under `~/.claude/projects/<cwd-slug>/reviews/` to open. Default `default`.
- `--port <port>` (optional): push to an already-running difit instance on this port instead of spawning a fresh one. Useful when the user has their own session open.

## Paths

```bash
PROJECT_DIR="$HOME/.claude/projects/$(pwd | sed 's:/:-:g')"
REVIEW_MD="$PROJECT_DIR/reviews/<name>/REVIEW.md"
```

If `REVIEW_MD` doesn't exist, error out with `Run /difit-review <name> first`.

## Verified facts about difit

- Difit argument order: `difit [commit-ish] [compare-with]` where `commit-ish` is the **new/target** side and `compare-with` is the **old/base** side. So to show feature branch (HEAD) vs master: `difit HEAD master` — NOT `difit master` (that would put master as the new side and show the diff in reverse).
- `difit <target> <base> --no-open --keep-alive --port <N>` starts a server bound to port `<N>` (pick a free port up front — difit doesn't auto-shift when `--port` is set). No `--background` needed when you control the port; see Step 2.
- `difit comment add --port <port> '<json-array>'` pushes new threads. There is no `--type` flag — omit it entirely.
- `difit comment add --type reply` is a silent no-op. Don't use it.
- The frontend persists full thread history (OP + replies) via `POST http://localhost:<port>/api/comments?base=<base>&target=<target>` with the **whole** threads payload. Use this when you need to seed prior replies, not just the OP.
- `difit comment get --format json [--port <port>]` reads the current state. With no `--port`, auto-discovers a single running instance.
- **The Claude Code sandbox kills difit.** Difit needs a long-lived process that outlives the spawning Bash call. The sandbox tears down the spawned process tree when the call returns, so a sandboxed spawn looks fine but the port is unreachable seconds later. Always pass `dangerouslyDisableSandbox: true` on the spawn call, and again on every later `comment add` / `comment get` call (those reach back into a network namespace the sandbox blocks).

## Step 1 — Read and parse REVIEW.md

Parse the YAML frontmatter:

```yaml
review_name: <slug>
ref: <descriptor>
base: <short sha or "HEAD">
target: <short sha or "working"/"staged">
diff_command: <git diff command used>
generated_at: <ISO 8601 with Z>
```

Then parse each `## <file>:<line>[-<end>] (<side>)` block:

- Header line → `filePath`, `position` (`{"side": "new", "line": 42}` or `{"side": "new", "line": {"start": 42, "end": 45}}`).
- Next non-empty line is `**<severity> · <reviewer> · <category>**` — keep as the body prefix.
- Body = everything between that line and the first `> **<Author> · <ts>...**` reply or the `---` separator.
- Each `> **<Author> · <ts>[ · <status>]**` followed by indented `> ` lines is a reply. Authors: `User` (typed in difit) or `Claude` (written by `/difit-resolve`). Status only on Claude replies: `applied`, `skipped`, `partial`, `question`.

A thread is **resolved** when its last message is a Claude reply with status `applied` or `skipped`. Filter these out — `/difit-open` only pushes unresolved threads.

A thread is **unresolved** if:
- No replies, or
- Last reply is from User (waiting on a Claude reply), or
- Last Claude reply has status `question` or `partial`.

## Step 2 — Reach difit

Resolution order:

1. **`--port <port>` argument** — verify reachable with `difit comment get --port <port> --format json > /dev/null 2>&1`. Error out if unreachable; don't silently fall back to spawning.
2. **`port:` field in REVIEW.md frontmatter** (written by a previous `/difit-open` run) — verify reachable the same way. If unreachable, ignore and continue to (3).
   A reachable instance is not always current — difit serves the diff it was spawned with, so a rebase, a new commit, or a `/difit-resolve` pass leaves it stale.
   Reuse it only if the frontmatter's `target` is a sha that still matches `git rev-parse --short HEAD`. If the sha moved, or `target` is `working` or `staged`, kill the frontmatter's `pid` and continue to (3).
3. **Spawn a fresh instance** from the frontmatter's `ref` field.

### Spawning a fresh instance

**Pick the port up front, fire-and-forget difit.** Don't use `--background` — its only purpose is to print JSON with the auto-assigned port, and once you choose the port yourself there's nothing to wait for. This also sidesteps the "harness backgrounds the call because it sees `--background`, you lose stdout, then sit polling a file" failure mode.

Pick a free port in the ephemeral range and verify nothing's listening:

```bash
for _ in 1 2 3 4 5; do
  PORT=$(( (RANDOM % 50000) + 10000 ))
  ss -tlnH "( sport = :$PORT )" | grep -q . || break
done
[[ -n "$PORT" ]] || { echo "no free port found"; exit 1; }
```

Map the frontmatter `ref` and resolved `base`/`target` SHAs to difit args. The universal pattern is `difit $TARGET $BASE` — target (new) first, base (old) second:

| frontmatter `ref` | difit invocation |
|---|---|
| `<a>..<b>` | `difit $TARGET $BASE --no-open --keep-alive --port $PORT` (i.e. `difit <b> <a>`) |
| `<rev>` | `difit $TARGET $BASE --no-open --keep-alive --port $PORT` (i.e. `difit HEAD <rev>`) |
| `working` / `.` | `difit . --no-open --keep-alive --port $PORT` |
| `staged` | `difit staged --no-open --keep-alive --port $PORT` |

Always prefer using the resolved SHA values from the REVIEW.md frontmatter (`base` / `target`) rather than symbolic names — this avoids ambiguity if branches have moved since the review was generated.

Spawn via the Bash tool with **both** `run_in_background: true` AND `dangerouslyDisableSandbox: true`. Sandbox-on kills the server; foreground blocks the skill. You don't need the spawn call's output at all — port is already known.

Wait briefly until the port is listening (~1-2 iterations on a warm machine):

```bash
for _ in $(seq 1 25); do
  ss -tlnH "( sport = :$PORT )" | grep -q . && break
  sleep 0.2
done
```

Capture the PID via pgrep:

```bash
PID=$(pgrep -f "difit.*--port $PORT" | head -1)
```

If `PID` is empty after the poll loop, difit failed to bind — surface stderr from the spawn task and stop.

**Write the resolved port and pid back into REVIEW.md's frontmatter** so `/difit-resolve` finds the instance without having to auto-discover or ask. Edit the existing `port:` / `pid:` lines (or add them if missing). Skip this write when `--port` was passed — the user is driving their own instance and the persisted port belongs to whatever spawned it.

## Step 3 — Push unresolved threads

Build the threads payload from the unresolved set. Two approaches depending on whether any unresolved thread has prior replies:

### 3a. OP-only threads → use `difit comment add`

If **none** of the unresolved threads have prior replies (typical for a fresh review where `/difit-resolve` hasn't run yet), push via the CLI — simpler:

```bash
difit comment add --port "$PORT" "$(cat /tmp/claude/threads-to-push.json)"
```

Payload entries:

```json
{
  "type": "thread",
  "filePath": "<file>",
  "position": {"side": "new", "line": 42},
  "body": "**<severity> · <reviewer> · <category>**\n\n<body>"
}
```

For multi-line: `"line": {"start": 42, "end": 45}`.

Response is `{"success":true,"importId":"...","count":N,"warnings":[]}`. **Fail loud** on non-empty `warnings` or `count != len(payload)` — print every warning verbatim.

### 3b. Threads with reply history → use frontend POST

If any unresolved thread has prior replies (e.g. user asked a follow-up, you're re-opening after a `/difit-resolve` that left questions), reconstruct the whole threads payload and POST it. This is the only way to seed multi-message threads — `difit comment add --type reply` is a no-op.

```python
import json, secrets, urllib.request
from datetime import datetime, timezone

PORT, BASE, TARGET = ...  # from Steps 1 + 2
threads = []
for t in unresolved_threads_from_review_md:
    messages = []
    # OP
    messages.append({
        "id": nanoid(),
        "body": f"**{t.severity} · {t.reviewer} · {t.category}**\n\n{t.body}",
        "createdAt": t.created_at, "updatedAt": t.created_at,
    })
    # Replies in order
    for r in t.replies:
        messages.append({
            "id": nanoid(), "body": r.body, "author": r.author,
            "createdAt": r.timestamp, "updatedAt": r.timestamp,
        })
    threads.append({
        "id": nanoid(),
        "filePath": t.file_path,
        "position": t.position,
        "createdAt": t.created_at, "updatedAt": messages[-1]["updatedAt"],
        "messages": messages,
    })

payload = {"version": 0, "threads": threads}
req = urllib.request.Request(
    f"http://localhost:{PORT}/api/comments?base={BASE}&target={TARGET}",
    data=json.dumps(payload).encode(), method="POST",
    headers={"Content-Type":"application/json",
             "Origin":f"http://localhost:{PORT}",
             "Referer":f"http://localhost:{PORT}/"})
with urllib.request.urlopen(req, timeout=10) as r:
    body = r.read().decode()
    if r.status != 200 or '"success":true' not in body:
        raise SystemExit(f"POST failed: {r.status} {body}")
```

`nanoid()`: 16 chars from `[a-z0-9]`. Use `secrets.choice` for entropy.

## Step 4 — Verify

Pull state back and check thread count matches what you sent:

```bash
N_PUSHED=<from step 3>
N_LIVE=$(difit comment get --port "$PORT" --format json | jq '.threads | length')
test "$N_LIVE" -ge "$N_PUSHED"  # allow >= so the user's pre-existing threads count too
```

If short: surface the discrepancy with the warnings array from `comment add` or the POST response body.

## Step 5 — Report

One line is enough:

> Opened review `<name>` on http://localhost:<port> (pid <pid>). N unresolved threads pushed.
> When done, run `/difit-resolve <name>` to apply the fixes and merge any new replies into REVIEW.md.

If you reused an existing instance (`--port` was given), say so:

> Pushed N unresolved threads to existing difit on http://localhost:<port>.

## What this skill does not do

- Doesn't write back to REVIEW.md (that's `/difit-resolve`'s job).
- Doesn't kill the difit instance — leave it running for the user.
- Doesn't filter by `--focus` or anything — REVIEW.md is already filtered.
