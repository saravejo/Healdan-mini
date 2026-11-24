#!/usr/bin/env python3
import argparse
import calendar
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}
OPEN_A = {"open", "in-progress", "blocked"}


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold().strip()


def add_months(d, n):
    month = d.month - 1 + n
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def resolve(expression, base):
    e = re.sub(r"\s+", " ", strip_accents(expression))
    e = re.sub(r"^(by|until|till|on|for|from|starting|before)\s+", "", e)
    r = lambda d, rule, ambiguous=False, alternative=None: {
        "expression": expression, "base": base.isoformat(), "date": d.isoformat(), "weekday": DAY_NAMES[d.weekday()],
        "rule": rule, "ambiguous": ambiguous, **({"alternative": alternative.isoformat()} if alternative else {})}

    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", e):
        return r(date(*map(int, m.groups())), "ISO date")
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", e):
        day, month, year = int(m[1]), int(m[2]), m[3]
        if year:
            return r(date(int(year) + (2000 if len(year) == 2 else 0), month, day), "date dd/mm/yyyy")
        d = date(base.year, month, day)
        return r(d if d >= base else date(base.year + 1, month, day), "dd/mm without year: next occurrence from the base")
    fixed = {"today": 0, "tomorrow": 1, "day after tomorrow": 2, "the day after tomorrow": 2, "yesterday": -1,
             "day before yesterday": -2, "the day before yesterday": -2}
    if e in fixed:
        return r(base + timedelta(days=fixed[e]), f"'{e}' from the base")
    if m := re.fullmatch(r"(?:in|within) (\d+|\w+) (days?|weeks?|months?)(?: from now)?", e):
        n = int(m[1]) if m[1].isdigit() else NUMBERS.get(m[1])
        if n is not None:
            unit = m[2]
            if unit.startswith("day"):
                return r(base + timedelta(days=n), f"base + {n} day(s)")
            if unit.startswith("week"):
                return r(base + timedelta(weeks=n), f"base + {n} week(s)")
            return r(add_months(base, n), f"base + {n} month(s)")
    if re.fullmatch(r"(?:the )?end of (?:the )?month", e):
        return r(date(base.year, base.month, calendar.monthrange(base.year, base.month)[1]), "last day of the base's month")
    if re.fullmatch(r"(?:the )?end of (?:the )?year", e):
        return r(date(base.year, 12, 31), "12/31 of the base's year")
    if m := re.fullmatch(r"(?:the )?(?:day (\d{1,2})|(\d{1,2})(?:st|nd|rd|th))", e):
        day = int(m[1] or m[2])
        d = base.replace(day=1)
        while True:
            if day <= calendar.monthrange(d.year, d.month)[1] and date(d.year, d.month, day) >= base:
                return r(date(d.year, d.month, day), "next day of the month with that number, counting the base")
            d = add_months(d, 1)
    if m := re.fullmatch(r"(next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", e):
        delta = (DAYS[m[2]] - base.weekday()) % 7
        if m[1]:
            delta = delta or 7
            d = base + timedelta(days=delta)
            return r(d, "next occurrence after the base", True, d + timedelta(days=7))
        return r(base + timedelta(days=delta), "next occurrence counting the base")
    if e in ("next week", "the next week"):
        d = base + timedelta(days=7 - base.weekday())
        return r(d, "Monday of the following week", True)
    return None


def find_root(start):
    for d in [start, *start.parents]:
        if (d / "CLAUDE.md").is_file() and (d / "2 - Wiki").is_dir():
            return d
    sys.exit("run inside the vault (could not find CLAUDE.md + 2 - Wiki/)")


def count(root):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_vault import frontmatter, notes

    today = date.today().isoformat()
    by_type, open_items, overdue, mature = {}, {"Q": 0, "A": 0}, [], []
    for p, _ in notes(root):
        fields, _ = frontmatter(p.read_text(encoding="utf-8"))
        if not fields or "id" not in fields:
            continue
        note_type, status = fields.get("type", "?"), fields.get("status", "?")
        by_type.setdefault(note_type, {}).setdefault(status, 0)
        by_type[note_type][status] += 1
        if note_type == "question" and status == "open":
            open_items["Q"] += 1
        if note_type == "activity" and status in OPEN_A:
            open_items["A"] += 1
            if fields.get("due") and fields["due"] < today:
                overdue.append(fields["id"])
        if note_type == "idea" and status == "mature":
            mature.append(fields["id"])
    inbox = [p for p in (root / "0 - Inbox").rglob("*") if p.is_file() and not p.name.startswith(".")]
    return {"today": today, "by_type": by_type, "open": open_items, "overdue_activities": sorted(overdue),
            "mature_ideas": sorted(mature), "inbox": len(inbox),
            "inbox_mcp": sum(1 for p in inbox if "mcp" in p.relative_to(root / "0 - Inbox").parts)}


def git(root, *args):
    output = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return output.stdout.strip() if output.returncode == 0 else "?"


def context(data):
    root = find_root(Path(data.get("cwd") or ".").resolve())
    now = datetime.now().astimezone()
    c = count(root)
    log = root / "log.md"
    latest = [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("## [")][-3:] if log.is_file() else []
    lines = [
        "Deterministic vault context (generated by facts.py; use these values instead of guessing):",
        f"- Now: {now:%Y-%m-%d %H:%M} ({DAY_NAMES[now.weekday()]}), timezone {now:%z}",
        f"- Branch: {git(root, 'branch', '--show-current')} | Claude session: {data.get('session_id', '?')}",
        f"- Inbox: {c['inbox']} file(s), {c['inbox_mcp']} from MCP",
        f"- Open: Q {c['open']['Q']} · A {c['open']['A']}"
        + (f" (overdue: {', '.join(c['overdue_activities'])})" if c["overdue_activities"] else "")
        + (f" · mature ideas: {', '.join(c['mature_ideas'])}" if c["mature_ideas"] else ""),
        "- Relative dates become absolute with: python3 .claude/scripts/facts.py date \"<expression>\" --base <YYYY-MM-DD>",
    ]
    if latest:
        lines.append("- Latest operations: " + " / ".join(l[3:] for l in latest))
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Deterministic data so the agent does not have to guess.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("now", help="local date and time, with timezone")
    d = sub.add_parser("date", help="converts a relative date into an absolute one")
    d.add_argument("expression")
    d.add_argument("--base", help="YYYY-MM-DD; default: today. Use the date of the message or document")
    e = sub.add_parser("epoch", help="converts a Unix timestamp (e.g. a Slack ts) into local date and time")
    e.add_argument("ts")
    sub.add_parser("count", help="counts by type and status, overdue activities, inbox")
    sub.add_parser("context", help="summary for the SessionStart hook (reads the hook JSON from stdin)")
    a = ap.parse_args()

    if a.cmd == "now":
        now = datetime.now().astimezone()
        print(json.dumps({"date": now.date().isoformat(), "time": f"{now:%H:%M:%S}", "timezone": f"{now:%z}",
                          "weekday": DAY_NAMES[now.weekday()], "iso": now.isoformat(timespec="seconds")},
                         ensure_ascii=False))
    elif a.cmd == "date":
        base = date.fromisoformat(a.base) if a.base else date.today()
        result = resolve(a.expression, base)
        if result is None:
            print(json.dumps({"expression": a.expression, "error": "not recognized: do not guess; leave the field empty or open a Q"},
                             ensure_ascii=False))
            return 1
        print(json.dumps(result, ensure_ascii=False))
    elif a.cmd == "epoch":
        moment = datetime.fromtimestamp(float(a.ts)).astimezone()
        print(json.dumps({"date": moment.date().isoformat(), "time": f"{moment:%H:%M:%S}", "timezone": f"{moment:%z}",
                          "iso": moment.isoformat(timespec="seconds")}, ensure_ascii=False))
    elif a.cmd == "count":
        print(json.dumps(count(find_root(Path.cwd())), ensure_ascii=False, indent=2))
    else:
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError:
            data = {}
        context(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
