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
and `git pull` are live:

```sh
git clone https://github.com/TrimVis/skills.git ~/git/skills
for d in ~/git/skills/*/; do
  name=$(basename "$d")
  ln -sfn "$d" ~/.claude/skills/"$name"
done
```

Skills are discovered automatically by Claude Code and invoked with
`/<skill-name>` or when their description matches a request.
