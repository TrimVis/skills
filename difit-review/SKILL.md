---
name: difit-review
description: Parallel multi-model code review. Spawns Opus, Sonnet, and Haiku reviewers in parallel — each specialised for the analysis dimensions that model is strongest at — then writes the merged findings to REVIEW.md under the Claude project dir. REVIEW.md is the authoritative review state; difit is a separate, optional viewer (use /difit-open after).
user-invocable: true
---

# Difit Review Skill

Three reviewers, three models, one diff. Findings get merged, deduped, and written to a per-review `REVIEW.md`. **This skill never touches difit** — that's `/difit-open`'s job.

## Arguments

- `ref` (optional, positional): git ref to review. Forms accepted:
  - omitted / `.` / `working` → unstaged + staged working tree
  - `staged` → staged only
  - `<rev>` → `<rev>..HEAD`
  - `<a>..<b>` → three-dot diff
  - `HEAD~n` → `HEAD~n..HEAD`
- `--name <slug>` (optional): review name for parallel reviews on the same repo. Default `default`. Must be filesystem-safe.
- `--focus <area>` (optional): narrow all reviewers to one of `security`, `performance`, `correctness`, `types`. Omit for default specialisation.
- `--force` (optional): overwrite an existing `REVIEW.md` at the same name.

## Paths

Compute once at start of skill:

```bash
PROJECT_DIR="$HOME/.claude/projects/$(pwd | sed 's:/:-:g')"
REVIEW_DIR="$PROJECT_DIR/reviews/<name>"
REVIEW_MD="$REVIEW_DIR/REVIEW.md"
```

Refuse to overwrite an existing non-empty `REVIEW_MD` unless `--force`. If the existing one has unresolved threads, mention how many before the refusal.

## Verified facts about the tools

- `difit comment get --format json` is the way to read difit state.
- `difit comment add --type thread '<json-array>'` works for pushing new threads. **`--type reply` is a silent no-op** — don't use it.
- The frontend persists replies via `POST http://localhost:<port>/api/comments?base=<base>&target=<target>` with the **whole** threads payload (GET, mutate, POST back). Returns `{"success":true}`.
- `difit <ref> --no-open --keep-alive --background` forks and prints one line of JSON: `{"port":N,"url":"http://localhost:N","pid":N}`. **Do not** wrap this in a backgrounded tool call — `--background` already forks and you lose the JSON.

## Step 1 — Diff capture

Resolve the ref to a diff:

| ref form | diff command | base | target |
|---|---|---|---|
| (none) / `.` / `working` | `git diff` + `git diff --cached` | `HEAD` short sha | `working` |
| `staged` | `git diff --cached` | `HEAD` short sha | `staged` |
| `<a>..<b>` | `git diff <a>...<b>` | `<a>` short sha | `<b>` short sha |
| `<rev>` | `git diff <rev>...HEAD` | `<rev>` short sha | `HEAD` short sha |
| `HEAD~n` | `git diff HEAD~n..HEAD` | `HEAD~n` short sha | `HEAD` short sha |

Resolve short SHAs with `git rev-parse --short <ref>` and stash them — the frontmatter and `/difit-open` need them.

Write the unified diff once to `$TMPDIR/difit-review-diff-<name>.patch`.

Read root `CLAUDE.md` plus any `CLAUDE.md` in directories the diff touches. Pass these to the reviewers as project rules.

## Step 2 — Spawn three reviewers in parallel

Send all three `Agent` calls in one message. Each gets the patch path, the changed file list, and the CLAUDE.md content. Each returns a strict JSON array — no prose, no markdown fences. Schema:

```json
[
  {
    "file": "path/to/file",
    "line": 42,
    "end_line": 45,
    "side": "new",
    "severity": "must-fix" | "suggestion" | "question",
    "category": "<reviewer's specialty>",
    "body": "Lead with the problem. Be specific and actionable."
  }
]
```

`end_line` omitted for single-line. `side` defaults to `"new"`; use `"old"` for comments on removed lines. Return `[]` if no findings.

Tell every reviewer: **line numbers come from the unified diff hunk headers**. Hallucinated line numbers will be dropped in Step 3. Repeat this in Haiku's prompt — it's the worst offender.

### Reviewer 1 — Opus (`model: opus`)

`subagent_type: general-purpose`. Focus:
- **Security**: injection, auth bypass, path traversal, SSRF, secrets in code, unsafe deserialisation, broken access control.
- **State/lifecycle**: missing cleanup, race conditions with a concrete trigger, ordering invariants, contextvar/global leaks.
- **Deep logic**: bugs that surface only when several lines or files are combined.

Categories: `security`, `lifecycle`, `logic`.

### Reviewer 2 — Sonnet (`model: sonnet`)

`subagent_type: general-purpose`. Focus:
- **Contracts**: changed signatures / return types / raised exceptions. **For any changed export, grep every caller and verify.**
- **Data flow**: nullability, lost type narrowing, branches the new code doesn't handle.
- **API boundaries**: request/response shape match between client and server, breaking changes to public exports.

Categories: `contract`, `dataflow`, `api`.

### Reviewer 3 — Haiku (`model: haiku`)

`subagent_type: general-purpose`. Focus:
- Missing imports, undefined references, typos.
- Unused imports / variables / functions.
- Off-by-one, wrong operator, swapped args, dead code.
- Mechanical CLAUDE.md style rules (line length, banned APIs, etc.).

Categories: `mechanical`, `naming`, `style`. Tell Haiku to skip anything needing more than local reasoning — Opus/Sonnet catch the rest.

## Step 3 — Aggregate and filter

1. Parse each reviewer's JSON. If one fails to parse, log it and continue with the other two.
2. Drop any finding whose `file` isn't in the diff (reviewers occasionally hallucinate paths).
3. Validate line numbers: `wc -l <file>` for each touched file; drop findings with out-of-range `line` / `end_line`. **If a `must-fix` was dropped, surface it in the final report.**
4. Dedupe: same `file` + line within ±2 AND same root issue → keep the highest-severity / most-specific version, prefix the body with `[opus + sonnet]` (or whichever pair).

## Step 4 — Write REVIEW.md

Format (round-trippable — `/difit-open` and `/difit-resolve` parse this back):

```markdown
---
review_name: <name>
ref: <ref descriptor>
base: <short sha or "HEAD">
target: <short sha or "working"/"staged">
diff_command: <exact git diff command>
generated_at: <ISO 8601 with Z>
# port and pid get filled in by /difit-open when it spawns difit; left blank here.
port:
pid:
---

# Review — <ref descriptor> — <generated_at>

## <file>:<line>[-<end_line>] (<side>)

**<severity> · <reviewer attribution> · <category>**

<body — one or more paragraphs, no leading `>`>

---

## <next thread>

...
```

Rules:
- Threads ordered by file, then line.
- The body of the OP is everything between the bold attribution line and the `---` separator (or next `## `). No replies yet on a fresh write.
- Severities map: `must-fix`, `suggestion`, `question`.
- Reviewer attribution: `opus`, `sonnet`, `haiku`, or `opus + sonnet` etc.

## Step 5 — Report

Two or three sentences:
- Path to `REVIEW.md`.
- Counts: `N must-fix, N suggestion, N question`.
- Per-reviewer counts and dedup overlap.
- Any dropped findings (especially `must-fix`), any reviewer that failed to return parseable JSON.
- Always end with: **`Next: /difit-open <name>` to review in browser**, or **`Next: /difit-resolve <name>` to apply the fixes directly**.

Example:

> Wrote 11 findings to `~/.claude/projects/-home-trim-...-/reviews/default/REVIEW.md` (4 must-fix, 6 suggestion, 1 question).
> Reviewers: opus 4 / sonnet 6 / haiku 3 — 1 dedup overlap. Dropped one haiku suggestion at `import_checkpoint.py:944` (file is 132 lines).
> Next: `/difit-open default` to review in browser.

## Fallback

If `difit` is not installed: this skill **still runs**. It writes `REVIEW.md` either way — difit is only consumed by `/difit-open`. Mention in the report that difit is missing if the user expected to use it.

## Notes on model selection

- Pass `model: opus | sonnet | haiku` explicitly on the Agent call.
- If a model errors, skip that reviewer and call it out in the report — don't fail the whole run.
- Do not pass `model: haiku` for the Sonnet role; Haiku can't reliably grep callers.

## What this skill is not

- Not a security audit (use `/security-review` for that).
- Not a fixer (use `/difit-resolve`).
- Does not start, push to, or touch difit (use `/difit-open`).
