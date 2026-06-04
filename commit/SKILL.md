---
name: commit
description: Create one or more focused commits from the current working tree. Groups changes by logical concern, writes terse category-prefixed headlines and short high-level descriptions. Authored as the user (no Claude co-author). Use when the user says "commit this", "make a commit", "commit my changes", or invokes /commit.
---

# Commit

Minimal commit workflow. Group sensibly, write short, ship.

## Authorship

Commits go out **in the user's name only**. Never add `Co-Authored-By: Claude` or any other trailer. Never pass `--author`. Use the existing git config.

## Step 1 — Inspect

Run in parallel:

- `git status` (no `-uall`)
- `git diff` (unstaged)
- `git diff --staged`
- `git log --oneline -15` to match existing prefix style

## Step 2 — Group

Split the working tree into the **smallest number of sensible commits**. Default to one commit. Split only when the changes serve clearly different concerns (e.g. a backend fix + an unrelated frontend tweak + a helm config bump).

Do **not**:
- Split a refactor from the behavior change it enables unless the user asked for that separation.
- Bundle untracked junk (logs, `.env`, MEDIA_ROOT uploads, cache files) — ask before staging anything suspicious.
- Use `git add -A` / `git add .`. Stage explicit paths.

## Step 3 — Message format

**Headline (≤72 chars):**

```
<category>: <what changed, imperative, lowercase after colon>
```

Pick the category from what the change actually touches. Look at recent `git log` for the conventions in use. Common ones in this repo: `backend:`, `frontend:`, `helm:`, `docs:`, `bugfix:`, `chore:`, `refactor:`, `chat agent:`, plus area-specific tags. If a change spans two areas cleanly, prefer splitting; if it genuinely doesn't, drop the prefix rather than inventing a hybrid.

**Body (optional, only if the headline isn't enough):**

- 1–3 short lines, high-level *why* not line-by-line *what*.
- No bullet lists of files changed. No restatement of the diff.
- Skip the body entirely for trivial changes.

Examples of good headlines (from this repo's history):
- `frontend: Simplify chat.js & eliminate dead code.`
- `bugfix: family background message partner`
- `docs: Add storage recommendations`

## Step 4 — Commit

For each group, in sequence:

1. Stage explicit paths: `git add path/one path/two`
2. Commit via heredoc to preserve formatting:

   ```bash
   git commit -m "$(cat <<'EOF'
   backend: fix profile creation when group missing

   Group lookup raised instead of creating; mirror the form path.
   EOF
   )"
   ```

3. If a pre-commit hook fails: fix the underlying issue, re-stage, make a **new** commit. Never `--amend` a failed commit. Never `--no-verify`.

4. After all commits: `git status` to confirm clean (or only intentionally-left-unstaged files remain).

## Don'ts

- No `Co-Authored-By` trailer. No "Generated with Claude Code".
- No `--amend` unless the user explicitly asks.
- No `git push`. Committing ≠ pushing.
- No emojis in commit messages.
- No multi-paragraph essays in the body.
