---
name: refine-skills
description: Mine Claude Code transcripts for how your installed skills actually behaved, find recurring corrections, and propose SKILL.md edits one finding at a time. Use when the user says "refine my skills", "improve my skills from usage", "what keeps going wrong with skill X", or invokes /refine-skills.
---

# Refine Skills

A correction the user retypes at every invocation is a default missing from the skill. This mines the transcripts for those and proposes the edit.

## Step 1 — Select

```
python3 ~/.claude/skills/refine-skills/skill-usage.py list
```

Show the table. Ask which skills to analyze by number, and accept `all`. Do not pick for the user.

Skills under ~5 episodes rarely yield a pattern. Say so and let the user decide.

## Step 2 — Extract

Per selected skill, all time:

```
python3 ~/.claude/skills/refine-skills/skill-usage.py extract <skill>
```

Read the output. Do not grep it for complaint words — that finds pasted test output, not complaints.

## Step 3 — Find

A finding needs **two or more episodes on different days**. One annoyed message is not a pattern.

Look for:

- **Repeated args.** The same instruction passed again and again (`--keep-alive`, `use a fable agent`, `also /commit`). The strongest signal, and the easiest to fix.
- **Chaining.** Args that name another skill (`and then /difit-open`) — the skill should offer or do the next step.
- **Retries.** `RETRIED after Nm` means the first run did not land.
- **Corrections.** Follow-up turns that redirect the run.

Then open the `SKILL.md` and confirm the gap is real. If the skill already says it and was ignored, the fix is wording or placement, not a new rule.

Confirm the fix is buildable before you propose it. A rule that reads state no tool exposes is dead on arrival, so check the CLI, the API, or the file format first. When only part of a finding is mechanizable, propose that part and say which part is not.

Ignore one-off task context (`push-api-2`, `mock-api`). That is the user steering, not the skill failing.

## Step 4 — Propose

One finding at a time, worst first. For each, show:

1. The finding and the episodes that support it (dates, quoted args).
2. A diff against the `SKILL.md`.

Ask to apply, skip, or edit. Apply the accepted diff, then move to the next finding. Never batch them.

Keep each edit to a few lines. These files are instructions and they get longer every pass, so replace a rule where you can instead of appending one.

## Don'ts

- Do not read whole transcripts into context. The script output is the input.
- Do not report a finding you cannot quote an episode for.
- Do not edit a skill the user did not select.
- Do not commit.
