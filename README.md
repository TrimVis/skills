# skills

Personal [Claude Code](https://claude.com/claude-code) skills.

Each top-level directory is one skill containing a `SKILL.md` (with YAML
frontmatter `name` + `description`) and any supporting files. The directory
name matches the skill name.

## Skills

| Skill | What it does |
|-------|--------------|
| [`commit`](commit/) | Create focused commits from the working tree, grouped by logical concern, with terse category-prefixed messages. Authored as the user. |
| [`squash`](squash/) | Rebase the current branch against its fork point and squash commits into a small, sensibly-grouped set. |
| [`difit-review`](difit-review/) | Parallel multi-model code review (Opus/Sonnet/Haiku) that writes merged findings to `REVIEW.md`. |
| [`difit-open`](difit-open/) | Open a `REVIEW.md` in difit's browser UI for interactive review. |
| [`difit-resolve`](difit-resolve/) | Apply fixes from a `REVIEW.md`, sync replies with a running difit instance. |
| [`refactor-prose`](refactor-prose/) | Iteratively refactor existing prose (policies, copy, docs) in place over multiple turns. |

## Install

Clone the repo and symlink each skill into your user skills directory so edits
and `git pull` are live. Set `SKILLS_REPO` to wherever you want the clone:

```sh
SKILLS_REPO="$HOME/git/skills"   # change to taste

git clone https://github.com/TrimVis/skills.git "$SKILLS_REPO"
for d in "$SKILLS_REPO"/*/; do
  ln -sfn "$d" "$HOME/.claude/skills/$(basename "$d")"
done
```

Skills are discovered automatically by Claude Code and invoked with
`/<skill-name>` or when their description matches a request.

## Dependencies

The `difit-*` skills drive [**difit**](https://github.com/yoshiko-pg/difit), a
browser-based git diff viewer, via its `difit` CLI. Install it before using
those skills:

```sh
npm install -g difit   # or run on demand with: npx difit
```

The other skills (`commit`, `squash`, `refactor-prose`) need only `git`.
