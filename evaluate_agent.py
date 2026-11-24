#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from new_id import find_root
from validate_vault import ID_RE, ids_by_name

FOLDER = "3 - Resources/agents/evaluations"
ORIGINS = ("self-assessment", "human-review")


def record(a, root):
    if not ID_RE.match(a.session) or not a.session.startswith("LS"):
        sys.exit(f"--session must be an LS id, got {a.session}")
    if a.session not in ids_by_name(root):
        sys.exit(f"note {a.session} does not exist: create the LS note before recording the evaluation")
    if a.origin == "self-assessment" and a.hallucinations_human:
        sys.exit("the self-assessment does not record hallucinations caught by the human: use --origin human-review")
    if a.origin == "human-review" and (a.hallucinations_subagent or a.hallucinations_session or a.checked):
        sys.exit("the human review records only what the human caught: --hallucinations-human and --unsupported")
    if a.unsupported > a.checked and a.origin == "self-assessment":
        sys.exit("--unsupported cannot exceed --checked")
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    n = 1 + sum(1 for _ in folder.glob(f"{a.session}-*.json"))
    destination = folder / f"{a.session}-{n}.json"
    entry = {
        "session": a.session,
        "date": date.today().isoformat(),
        "origin": a.origin,
        "claims_checked": a.checked,
        "unsupported": a.unsupported,
        "hallucinations": {"subagent": a.hallucinations_subagent, "session": a.hallucinations_session, "human": a.hallucinations_human},
        "note": a.note,
    }
    with open(destination, "x", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    print(destination.relative_to(root))


def report(a, root):
    by_session = {}
    for file in sorted((root / FOLDER).glob("*.json")):
        r = json.loads(file.read_text(encoding="utf-8"))
        if a.since and r["date"] < a.since:
            continue
        s = by_session.setdefault(r["session"], {"date": r["date"], "chk": 0, "uns": 0, "sub": 0, "ses": 0, "hum": 0})
        s["date"] = min(s["date"], r["date"])
        s["chk"] += r["claims_checked"]
        s["uns"] += r["unsupported"]
        s["sub"] += r["hallucinations"]["subagent"]
        s["ses"] += r["hallucinations"]["session"]
        s["hum"] += r["hallucinations"]["human"]
    lines = [
        f"| Session | Date | Checked | Unsupported | Hallucinations (sub/session/{a.human}) | Hallucination rate |",
        "|---|---|---|---|---|---|",
    ]
    total = {"chk": 0, "uns": 0, "sub": 0, "ses": 0, "hum": 0}
    for session, s in sorted(by_session.items(), key=lambda kv: (kv[1]["date"], kv[0])):
        for k in total:
            total[k] += s[k]
        lines.append(row(session, s["date"], s))
    lines.append(row("**Total**", "", total))
    output = "\n".join(lines)
    if a.output:
        Path(a.output).write_text(output + "\n", encoding="utf-8")
    print(output)


def row(name, day, s):
    halluc = s["sub"] + s["ses"] + s["hum"]
    rate = f"{halluc / s['chk']:.1%}" if s["chk"] else "n/a"
    return f"| {name} | {day} | {s['chk']} | {s['uns']} | {s['sub']}/{s['ses']}/{s['hum']} | {rate} |"


def main():
    ap = argparse.ArgumentParser(description="Layer 1 against hallucination: evaluation of each agent session.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("record")
    g.add_argument("--session", required=True)
    g.add_argument("--origin", choices=ORIGINS, default="self-assessment")
    g.add_argument("--checked", type=int, default=0)
    g.add_argument("--unsupported", type=int, default=0)
    g.add_argument("--hallucinations-subagent", type=int, default=0)
    g.add_argument("--hallucinations-session", type=int, default=0)
    g.add_argument("--hallucinations-human", type=int, default=0)
    g.add_argument("--note", default="")
    r = sub.add_parser("report")
    r.add_argument("--since", help="YYYY-MM-DD")
    r.add_argument("--human", default="human", help="label for the reviewer's column (e.g. your name)")
    r.add_argument("--output", help="also writes the table to this file")
    a = ap.parse_args()
    if any(v < 0 for k, v in vars(a).items() if isinstance(v, int)):
        sys.exit("counts cannot be negative")
    root = find_root()
    record(a, root) if a.cmd == "record" else report(a, root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
