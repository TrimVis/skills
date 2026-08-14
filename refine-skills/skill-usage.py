#!/usr/bin/env python3
"""Mine Claude Code transcripts for how installed skills actually get used.

  skill-usage.py list                    numbered table of skills by invocation count
  skill-usage.py extract <skill> [days]  every episode: args, follow-up turns, retries
"""
import json, os, re, sys, glob
from collections import defaultdict
from datetime import datetime, timezone, timedelta

PROJECTS = os.path.expanduser("~/.claude/projects")
SKILLS = os.path.expanduser("~/.claude/skills")
CMD = re.compile(r"<command-name>/([a-zA-Z0-9_-]+)</command-name>")
ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
NOISE = ("Base directory for this skill", "<command-message>", "<command-name>",
         "(Re-invocation of", "<local-command", "<system-reminder>", "Caveat:",
         "<user-prompt-submit-hook>", "<task-notification>", "<task-id>",
         "[Request interrupted", "API Error", "Skill /")
WINDOW = 80          # records scanned after an invocation
RETRY_MIN = 30       # re-invocation within N minutes counts as a retry

# Built-in CLI commands share the /slash syntax but are not skills.
BUILTIN = {
    "add-dir", "agents", "bug", "clear", "compact", "config", "context", "cost", "doctor",
    "exit", "export", "fast", "feedback", "goal", "help", "hooks", "ide", "init",
    "install-github-app", "loop", "login", "logout", "mcp", "memory", "migrate-installer",
    "model", "output-style", "permissions", "plan", "pr-comments", "privacy-settings",
    "release-notes", "reload-skills", "remote-env", "resume", "review", "rewind",
    "schedule", "skills", "status", "statusline", "terminal-setup", "todos", "upgrade",
    "usage", "vim", "workflows",
}


def installed():
    return {n for n in os.listdir(SKILLS) if not n.startswith(".")}


def blocks(content):
    if isinstance(content, str):
        return [("text", content)]
    out = []
    for c in content or []:
        if not isinstance(c, dict):
            continue
        t = c.get("type")
        if t == "text":
            out.append(("text", c.get("text", "")))
        elif t == "thinking":
            out.append(("thinking", c.get("thinking", "")))
        elif t == "tool_result":
            out.append(("tool_result", ""))
        elif t == "tool_use":
            out.append(("tool_use", json.dumps({"name": c.get("name"), "input": c.get("input")})))
    return out


def typed_user_text(d):
    """The user's own typed text. None for tool results and injected preambles."""
    if d.get("type") != "user" or d.get("isSidechain"):
        return None
    bs = blocks((d.get("message") or {}).get("content"))
    if any(k == "tool_result" for k, _ in bs):
        return None
    txt = "\n".join(v for k, v in bs if k == "text").strip()
    return None if not txt or txt.startswith(NOISE) else txt


def invocation(d, skill=None):
    """Return (skill, args) if this record invokes a skill, else None."""
    msg = d.get("message") or {}
    if d.get("type") == "assistant":
        for c in msg.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
                s = (c.get("input") or {}).get("skill")
                if s and (skill is None or s == skill):
                    return s, ((c.get("input") or {}).get("args") or "")
    if d.get("type") == "user":
        raw = "\n".join(v for k, v in blocks(msg.get("content")) if k == "text")
        for m in CMD.finditer(raw):
            if skill is None or m.group(1) == skill:
                a = ARGS.search(raw)
                return m.group(1), (a.group(1).strip() if a else "")
    return None


def load(path):
    recs = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if '"Skill"' not in line and "command-name" not in line \
               and '"type":"user"' not in line and '"type": "user"' not in line:
                recs.append(None)
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                recs.append(None)
    return recs


def episodes(skill, days=None):
    """All episodes for one skill, deduped across resumed-session forks."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    by_key = {}
    for path in sorted(glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))):
        recs = load(path)
        for i, d in enumerate(recs):
            if d is None:
                continue
            inv = invocation(d, skill)
            if inv is None:
                continue
            ts = d.get("timestamp") or ""
            if cutoff and ts:
                try:
                    if datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                        continue
                except Exception:
                    pass
            follow, retry = [], None
            for e in recs[i + 1: i + 1 + WINDOW]:
                if e is None:
                    continue
                nxt = invocation(e, skill)
                if nxt is not None:
                    try:
                        dt = datetime.fromisoformat((e.get("timestamp") or "").replace("Z", "+00:00")) \
                             - datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt <= timedelta(minutes=RETRY_MIN):
                            retry = int(dt.total_seconds() // 60)
                    except Exception:
                        pass
                    break
                t = typed_user_text(e)
                if t:
                    follow.append(t)
            ep = {"ts": ts, "file": os.path.basename(path), "cwd": d.get("cwd", ""),
                  "args": inv[1], "follow": follow, "retry": retry}
            # Resumed sessions duplicate whole episodes; keep the richest copy.
            key = (ts, inv[1][:80])
            if key not in by_key or len(follow) > len(by_key[key]["follow"]):
                by_key[key] = ep
    return sorted(by_key.values(), key=lambda e: e["ts"])


def counts():
    known, tally = installed(), defaultdict(lambda: {"all": 0, "week": 0, "sess": set()})
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for path in sorted(glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))):
        for d in load(path):
            if d is None:
                continue
            inv = invocation(d)
            if inv is None:
                continue
            s, ts = inv[0], (d.get("timestamp") or "")
            t = tally[s]
            t["all"] += 1
            t["sess"].add(path)
            try:
                if datetime.fromisoformat(ts.replace("Z", "+00:00")) >= cutoff:
                    t["week"] += 1
            except Exception:
                pass
    return known, tally


def cmd_list():
    known, tally = counts()
    rows = sorted(((s, v) for s, v in tally.items() if v["all"] and s not in BUILTIN),
                  key=lambda kv: -kv[1]["all"])
    w = max([len(s) for s, _ in rows] + [12]) + 2
    print(f"  {'#':>2}  {'skill':<{w}} {'all-time':>8} {'7d':>4} {'sessions':>8}")
    n = 0
    for s, v in rows:
        n += 1
        mark = "" if s in known else "   (not installed)"
        print(f"  {n:>2}  {s:<{w}} {v['all']:>8} {v['week']:>4} {len(v['sess']):>8}{mark}")
    zero = sorted(known - set(tally))
    if zero:
        print(f"\n  {len(zero)} installed skills with 0 invocations: {', '.join(zero)}")


def cmd_extract(skill, days=None):
    eps = episodes(skill, days)
    with_args = sum(1 for e in eps if e["args"])
    print(f"### {skill} — {len(eps)} episodes, {with_args} with args, "
          f"{sum(len(e['follow']) for e in eps)} typed follow-ups, "
          f"{sum(1 for e in eps if e['retry'] is not None)} retries\n")
    for e in eps:
        print(f"[{e['ts'][:16]}] {e['cwd']}" + (f"  RETRIED after {e['retry']}m" if e["retry"] is not None else ""))
        if e["args"]:
            print(f"   ARGS: {e['args'][:400]}")
        for t in e["follow"][:4]:
            print(f"   USER: {t[:500]}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        cmd_list()
    elif sys.argv[1] == "extract":
        cmd_extract(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
