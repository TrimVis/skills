---
name: difit-resolve
description: Apply the fixes proposed in a REVIEW.md (written by /difit-review), merge any new user replies from a running difit instance, write Claude's replies back into REVIEW.md, and best-effort echo them to difit if it's running. REVIEW.md is the source of truth; difit is an optional UI we sync to when available.
user-invocable: true
---

# Difit Resolve Skill

Read `REVIEW.md`, pull any new user replies from a running difit (if there is one), apply the fixes, append Claude replies into `REVIEW.md`, push the augmented state back to difit (if still reachable). `REVIEW.md` is authoritative — every reply lands in the file. Difit is best-effort: if it's running we sync, if it's not we don't; if it's running but rejects messages we **fail loud**.

## Arguments

- `name` (optional, positional): which review to resolve. Default `default`.
- `--port <port>` (optional): difit instance to sync to. If omitted, auto-discover a single running instance.
- `--no-difit` (optional): skip the difit sync entirely. Useful when you only want to fix from `REVIEW.md` without touching the browser session.

## Paths

```bash
PROJECT_DIR="$HOME/.claude/projects/$(pwd | sed 's:/:-:g')"
REVIEW_MD="$PROJECT_DIR/reviews/<name>/REVIEW.md"
```

If `REVIEW_MD` is missing, error out with `Run /difit-review <name> first`.

## Verified facts about difit (v5.0.1)

- `difit comment get --format json --port <port>` reads current state. `--port` is **required** (not auto-discovered).
- `difit comment add --type reply` is a **silent no-op**. Always use the frontend POST for replies.
- `POST http://localhost:<port>/api/comments` (NO query params) with `{threads: [...]}` is how replies persist. Returns `{"success":true}` on a 200.
- **Critical**: do **not** add `?base=<sha>&target=<sha>` to the POST URL. difit keys sessions by full SHAs internally, and short SHAs in query params spawn a fresh empty session your write silently lands in — the server still returns `{"success":true}` and the GET (which uses the active session) shows nothing changed. Omit the query params; the server uses its current selection.
- difit's session storage is in-memory and lives per `(base, target)` selection. A fresh `--background` instance for the same ref reuses its session as long as the process is up.

## Step 1 — Read REVIEW.md

Parse the frontmatter and threads same as `/difit-open` does. Stash `port` (from frontmatter), `base`, `target`, and the parsed thread list (including any prior replies).

A thread is **resolved** when its last message is a Claude reply with status `applied` or `skipped`. Skip resolved threads in Step 3.

## Step 2 — Pull difit state (unless `--no-difit`)

Port resolution order:

1. `--port <port>` argument.
2. `port:` field from the REVIEW.md frontmatter (written by `/difit-open`).
3. Ask via `AskUserQuestion` — don't guess.

Verify:

```bash
DIFIT_STATE=$(difit comment get --port <port> --format json 2>&1)
```

Outcomes:

| Result | Action |
|---|---|
| Valid JSON with threads | Proceed to merge new user replies. |
| Connection refused / port unreachable | If the port came from the frontmatter, treat as "difit not running" (the user killed it); continue without sync. If the user gave the port explicitly, **fail loud**. |
| Any other error | **Fail loud** — print the stderr verbatim and stop. |

Track which case we're in as `DIFIT_AVAILABLE` (yes / no).

### 2a. Merge new user replies into REVIEW.md (only when `DIFIT_AVAILABLE`)

Index difit threads by `(filePath, position)`. For each thread in REVIEW.md:

1. Find the matching difit thread by the same key.
2. For every message in the difit thread:
   - If `author == "User"` AND no message in REVIEW.md for this thread has a matching `(author=User, body, createdAt)` — it's new.
   - Append it to REVIEW.md as a `> **User · <createdAt>**` block.

If a difit thread exists for a `(filePath, position)` that REVIEW.md doesn't have — surface as a warning (`User added a comment difit didn't seed`). Don't drop it; record it as a thread under a `## New (from difit)` section in REVIEW.md so the user knows it landed.

Re-read your own REVIEW.md after writing so the rest of the skill sees the merged state.

## Step 3 — Apply each unresolved fix

For each unresolved thread, in file-then-line order:

1. The **authoritative instruction** is the last User reply (if any), otherwise the OP body. Quote it in your reply if it differs from the OP (e.g. OP said "add a TimeoutError handler" but User said "actually just propagate"; you follow User).
2. Read the referenced file at the cited line range.
3. Decide:
   - **Actionable** → apply with Edit. Status: `applied`.
   - **Partial** (multi-ask comment where part is in scope and part needs design) → apply what you can. Status: `partial`. Spell out in the reply which parts landed and which you deferred.
   - **Skip** (vague / conflicts with another fix / asks for something you can't do safely) → don't edit. Status: `skipped`. Quote the reason.
   - **Question** (genuinely ambiguous, needs human direction) → don't edit. Status: `question`.
4. If the OP severity was `must-fix` and you `skipped`, surface it in the final report — don't bury it.

Keep edits tight. Do not refactor surrounding code or "improve" things the comment didn't ask for.

## Step 4 — Verify edits

After all fixes:

1. Run any obvious type checker / linter (`ruff check`, `tsc --noEmit`, `cargo check`, etc.). Skip if no obvious command.
2. Run tests adjacent to what you touched.
3. Re-read each touched file once.

If verification surfaces a problem caused by your edit, downgrade that thread's reply status to `applied-with-issue` and quote the error in the body. Don't hide it.

## Step 5 — Append Claude replies to REVIEW.md

For every thread you handled (applied / partial / skipped / question), append a reply block:

```markdown
> **Claude · 2026-05-27T15:42Z · applied**
> Replaced fallback with direct access at L34-L35; also dropped now-unused
> `import os` at L7.
```

Status values:
- `applied`: fix landed clean.
- `partial`: some of the asks landed; quote which.
- `skipped`: nothing changed; quote the reason.
- `question`: needs human input; quote what.
- `applied-with-issue`: edit landed but Step 4 found a regression.

Reply body is one short paragraph. Reference file:line if helpful. Quote the user's reasoning when honoring a `User` directive that overrode the OP.

Write the entire augmented REVIEW.md (frontmatter unchanged, threads with new replies). This is the only durable record — get it right.

## Step 6 — Sync back to difit (when `DIFIT_AVAILABLE`)

Use the packaged helper `sync_replies.py` (sits next to this SKILL.md):

```bash
SKILL_DIR="$HOME/.claude/skills/difit-resolve"
python3 "$SKILL_DIR/sync_replies.py" --port "$PORT" --replies /tmp/claude/replies.json
```

The replies JSON is a list of `{filePath, position, body}` objects, one per Claude reply you wrote in Step 5. `position` matches the format in REVIEW.md (`{"line": 42}` or `{"line": {"start": 12, "end": 18}}`). `body` is the markdown reply text — the `**applied** ...` / `**skipped** ...` / etc. tag goes at the start so the next `/difit-resolve` run can parse it back.

Exit codes:
- `0` — all replies appended (or already present and skipped as duplicates).
- `1` — difit unreachable, or POST rejected. **Fail loud** — surface stderr.
- `2` — one or more replies didn't match a thread on the server (server-side thread missing). Print which and continue, but flag in Step 7.

Verify after the helper succeeds:

```bash
LIVE_CLAUDE_REPLIES=$(difit comment get --port "$PORT" --format text | grep -c '^Reply [0-9]* (Claude)')
```

Should equal the count you intended. If short, fail loud and report the discrepancy in Step 7.

## Step 7 — Report

Tell the user:
- How many threads were processed: counts for `applied`, `partial`, `skipped`, `question`, `applied-with-issue`.
- For each `must-fix` you skipped: file:line and one-line reason.
- For each `question`: file:line and the question — they need to reply and re-run.
- The state of the difit sync: synced N, or "difit not running so REVIEW.md is the only record".
- If the difit sync was attempted and short / failed: surface the count mismatch + the warnings.
- The path to `REVIEW.md` is always sufficient as the audit trail.

Example (difit running):

> Resolved 11/17 threads (4 applied, 2 partial, 5 skipped, 1 question). All Claude replies written to `~/.claude/projects/.../reviews/default/REVIEW.md`. Synced to difit (11/11 replies live).
>
> Skipped (must-fix):
> - `src/api.ts:88` — comment asked to "rework error handling"; needs your shape decision
>
> Question:
> - `src/auth.ts:23` — "is this intentional or leftover from the old flow?"

Example (difit not running):

> Resolved 11/17 threads (4 applied, 2 partial, 5 skipped, 1 question). All replies in REVIEW.md. difit not running; reopen with `/difit-open default` to see the audit trail in browser.

## What this skill does not do

- Doesn't start difit (use `/difit-open`).
- Doesn't trust difit replies that aren't already in REVIEW.md without writing them through (Step 2a copies them into the file before acting on them).
- Doesn't silently drop a difit failure when difit is reachable. If `comment get` works but the POST doesn't, that's a loud error.
