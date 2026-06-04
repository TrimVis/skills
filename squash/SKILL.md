---
name: squash
description: Rebase the current branch against its fork point (master/main) and squash the branch commits into a small, sensibly-grouped set. Larger restructuring is welcome — drop work that was later reverted, fold fixups into their parent. Commit messages follow the same category-prefixed terse style as /commit, authored as the user. Use when the user says "squash this branch", "clean up commits", "squash before merge", or invokes /squash.
---

# Squash

Collapse a feature branch into a clean, reviewable history before merge.

## Authorship

All resulting commits in the user's name only. No `Co-Authored-By: Claude`. No `--author`. Preserve whatever the user already had; don't rewrite identity.

## Step 1 — Find the fork point

Determine the base branch (usually `master`, sometimes `main`). Check what exists:

```bash
git rev-parse --verify master 2>/dev/null || git rev-parse --verify main
```

Find the actual fork point (not just `master` HEAD, which may have moved):

```bash
git merge-base HEAD <base>
```

Show the user the branch range before doing anything:

```bash
git log --oneline <base>..HEAD
git diff --stat <base>...HEAD
```

## Step 2 — Safety check

Before rewriting history:

- [ ] Working tree is clean (`git status`). If not, stop and ask.
- [ ] Branch is **not** `master`/`main` itself.
- [ ] Note whether the branch is pushed (`git rev-parse @{u}` succeeds). If yes, warn the user that this will require a force-push and confirm before proceeding.
- [ ] Create a safety ref so the pre-squash state is recoverable:
  ```bash
  git branch backup/squash-<branch>-<shortsha>
  ```
  Tell the user the backup ref name.

## Step 3 — Plan the squash

Read the branch's commits and the cumulative diff. Decide the **final commit set**.

Guiding principles:

- **Default to one commit.** Only split when the branch genuinely does multiple independent things that a reviewer would want to evaluate separately (e.g. a backend change + an unrelated helm bump).
- **Drop reverted work.** If a feature was added and later removed within the branch, the final history should contain neither — not "add X" followed by "remove X".
- **Fold fixups.** "fix typo", "address review", "oops" → into their logical parent.
- **Restructure freely.** This is the moment for it. The branch's intermediate history is throwaway.
- **Respect the user's intent.** If the branch clearly tells a story across 2–3 commits the user constructed deliberately, don't flatten it without asking.

Present the plan to the user before rewriting:

```
Squashing 14 commits into 2:
  1. backend: <headline>   (folds: a1b2c3, d4e5f6, ...)
  2. frontend: <headline>  (folds: 7a8b9c, ...)
Dropping: "add experimental flag X" (reverted in same branch)
Backup: backup/squash-<branch>-<sha>
```

Wait for confirmation unless the user pre-authorized.

## Step 4 — Execute

Prefer the **soft reset** approach over `rebase -i` — it's mechanical, scriptable, and avoids editor interaction.

For a single resulting commit:

```bash
git reset --soft $(git merge-base HEAD <base>)
git commit -m "$(cat <<'EOF'
<category>: <headline>

<optional short body>
EOF
)"
```

For multiple resulting commits, do it in passes: soft-reset to base, then stage and commit each logical group with explicit `git add <paths>`.

If conflicts surface during a true rebase (only needed if you also want to land on top of updated `<base>`):

```bash
git rebase <base>
```

Resolve them; never `--skip` past a conflict without understanding it. Never use destructive escapes (`rebase --abort` is fine and non-destructive; `reset --hard` to discard is not).

## Step 5 — Commit message rules

Identical to `/commit`:

- Headline ≤72 chars, `<category>: <imperative summary>`.
- Categories from recent `git log` (`backend:`, `frontend:`, `helm:`, `docs:`, `bugfix:`, `chore:`, `refactor:`, ...).
- Body optional, 1–3 short lines, high-level *why*.
- No bullet-list of folded commits. No "squashed from N commits". The history itself shows that.
- No emojis. No `Co-Authored-By`.

## Step 6 — Verify

```bash
git log --oneline <base>..HEAD
git diff <base>...HEAD --stat
```

Confirm the cumulative diff is **identical** to before the squash:

```bash
git diff <pre-squash-backup>..HEAD   # should be empty
```

If non-empty, something was lost — reset to the backup ref and re-plan.

## Step 7 — Push (only if asked)

If the branch was previously pushed and the user wants it updated:

```bash
git push --force-with-lease
```

Never plain `--force`. Never force-push to `master`/`main`. Confirm before pushing even with `--force-with-lease` if you haven't already.

## Don'ts

- No `Co-Authored-By` trailer.
- No force-push without explicit confirmation.
- No squashing on `master`/`main`.
- No silent dropping of commits the user might want — surface the plan first.
- No `git push --force` (use `--force-with-lease`).
