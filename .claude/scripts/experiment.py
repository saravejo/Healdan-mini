#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from eval_skills import affected, evaluate
from measure_agent import DEFAULT_CONFIG, run
from new_id import find_root

SURFACE = ("CLAUDE.md", ".claude/rules/", ".claude/skills/", ".claude/agents/", "3 - Resources/templates/")
FOLDER = "3 - Resources/evals/results/experiments"
MIN_NOISE = 0.02
LINE_LIMIT = 40
COST_LIMIT = 0.25
PREFIX = "experiment:"


def git(root, *args, check=True):
    output = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and output.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{output.stderr}")
    return output.stdout.strip()


def surface_lines(root):
    total = 0
    for item in SURFACE:
        target = root / item
        paths = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()] if target.is_dir() else []
        for p in paths:
            try:
                total += len(p.read_text(encoding="utf-8").splitlines())
            except UnicodeDecodeError:
                pass
    return total


def entries(root, tag):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / FOLDER).glob(f"{tag}-*.json"))]


def record(root, entry, message, extras=()):
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{entry['tag']}-{entry['n']:03d}.json"
    with open(destination, "x", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    git(root, "add", "--", str(destination.relative_to(root)), *[str(Path(e).relative_to(root)) for e in extras])
    git(root, "commit", "-q", "-m", f"{PREFIX} {message}")
    return destination


def validate(root):
    return subprocess.run([sys.executable, str(Path(__file__).with_name("validate_vault.py"))], cwd=root,
                          capture_output=True, text=True).returncode == 0


def decide(delta, noise, delta_lines, delta_cost):
    if delta >= 2 * noise:
        return "keep", "large gain"
    if delta >= noise:
        if delta_lines > LINE_LIMIT:
            return "discard", f"small gain does not pay for +{delta_lines} lines"
        if delta_cost > COST_LIMIT:
            return "discard", f"small gain does not pay for +{delta_cost:.0%} cost"
        return "keep", "gain above the noise"
    if delta > -noise and delta_lines < 0 and delta_cost <= COST_LIMIT:
        return "keep", "simplification with the same score"
    if delta <= -noise:
        return "discard", "got worse"
    return "discard", "tie without simplification"


def eval_touched_skills(root, extras):
    changed = git(root, "diff", "--name-only", "HEAD~1", "HEAD").splitlines()
    touched = affected(root, changed, "HEAD", shared=False)
    if not touched:
        return []
    try:
        passed, paths = evaluate(root, touched, ref="HEAD", yardstick="main")
    except RuntimeError as error:
        return [f"{', '.join(touched)} (the eval did not run: {error})"]
    extras += paths
    return [] if passed else touched


def cost(summary):
    return summary.get("cost_usd") or 0.0


def start(root, tag, config, parallel):
    if git(root, "status", "--porcelain"):
        sys.exit("start with a clean tree: commit or stash what is pending")
    git(root, "switch", "-q", "-c", f"experiment/{tag}", "main")
    if not validate(root):
        sys.exit("the vault does not pass the validator: fix it before measuring the baseline")
    r1, _, p1 = run(root, config, parallel=parallel)
    r2, _, p2 = run(root, config, parallel=parallel)
    if r1["errors"] or r2["errors"] or r1["invented_ids"] or r2["invented_ids"] or None in (r1["score"], r2["score"]):
        sys.exit("the baseline needs 0 errors and 0 invented IDs in both runs")
    noise = max(MIN_NOISE, round(abs(r1["score"] - r2["score"]), 4))
    entry = {
        "tag": tag, "n": 0, "date": datetime.now().isoformat(timespec="seconds"), "status": "baseline",
        "description": "baseline (two runs)", "commit": git(root, "rev-parse", "--short", "HEAD"),
        "score": round((r1["score"] + r2["score"]) / 2, 4), "noise": noise, "lines": surface_lines(root),
        "cost_usd": round((cost(r1) + cost(r2)) / 2, 4), "config": r1["config"],
    }
    record(root, entry, f"{tag} baseline", (p1, p2))
    print(f"baseline: score {entry['score']}, noise {noise}, {entry['lines']} lines on the surface")


def measure(root, description, parallel):
    branch = git(root, "branch", "--show-current")
    if not branch.startswith("experiment/"):
        sys.exit("run on an experiment/<tag> branch created by `experiment.py start`")
    tag = branch.split("/", 1)[1]
    regs = entries(root, tag)
    if not regs:
        sys.exit("no baseline: run `experiment.py start <tag>`")
    if git(root, "status", "--porcelain"):
        sys.exit("commit your single change before measuring")
    last_entry = git(root, "log", "-1", "--format=%H", f"--grep=^{PREFIX}")
    if int(git(root, "rev-list", "--count", f"{last_entry}..HEAD")) != 1:
        sys.exit("an experiment is exactly one commit after the last entry")
    base = next(r for r in reversed(regs) if r["status"] in ("baseline", "keep"))
    commit = git(root, "rev-parse", "--short", "HEAD")
    outside = [f for f in git(root, "diff", "--name-only", "HEAD~1", "HEAD").splitlines() if not f.startswith(SURFACE)]
    entry = {"tag": tag, "n": regs[-1]["n"] + 1, "date": datetime.now().isoformat(timespec="seconds"),
             "description": description, "commit": commit, "base": base["n"], "noise": base["noise"], "config": base["config"]}
    extras = []
    if outside:
        entry |= {"status": "off-surface", "reason": f"changed {outside}"}
    elif not validate(root):
        entry |= {"status": "crash", "reason": "the validator failed"}
    elif failed := eval_touched_skills(root, extras):
        entry |= {"status": "crash", "reason": f"skill eval failed: {', '.join(failed)}"}
    else:
        summary, _, path = run(root, base["config"], parallel=parallel)
        extras.append(path)
        lines = surface_lines(root)
        entry |= {"score": summary["score"], "lines": lines, "cost_usd": cost(summary),
                  "invented_ids": summary["invented_ids"]}
        if summary["errors"] or summary["invented_ids"] or summary["score"] is None:
            entry |= {"status": "crash", "reason": f"{summary['errors']} error(s), {summary['invented_ids']} invented ID(s)"}
        else:
            delta = round(summary["score"] - base["score"], 4)
            delta_lines = lines - base["lines"]
            delta_cost = (cost(summary) - base["cost_usd"]) / base["cost_usd"] if base["cost_usd"] else 0.0
            status, reason = decide(delta, base["noise"], delta_lines, delta_cost)
            entry |= {"status": status, "reason": reason, "delta": delta, "delta_lines": delta_lines,
                      "delta_cost": round(delta_cost, 4)}
    if entry["status"] != "keep":
        git(root, "revert", "--no-edit", "HEAD")
        entry["reverted_in"] = git(root, "rev-parse", "--short", "HEAD")
    record(root, entry, f"{tag}-{entry['n']:03d} {entry['status']}: {description}", extras)
    print(f"{entry['status']}: {entry.get('reason', '')} | score {entry.get('score')} "
          f"(Δ {entry.get('delta')}, noise {base['noise']}) | lines Δ {entry.get('delta_lines')}")


def report(root, tag):
    regs = entries(root, tag)
    print("| n | commit | status | score | Δ score | Δ lines | Δ cost | description |")
    print("|---|---|---|---|---|---|---|---|")
    for r in regs:
        dc = f"{r['delta_cost']:+.0%}" if r.get("delta_cost") is not None else ""
        print(f"| {r['n']} | {r['commit']} | {r['status']} | {r.get('score', '')} | {r.get('delta', '')} | "
              f"{r.get('delta_lines', '')} | {dc} | {r['description']} |")
    count = {}
    for r in regs[1:]:
        count[r["status"]] = count.get(r["status"], 0) + 1
    print(f"\n{len(regs) - 1} experiment(s): {count}")


def main():
    ap = argparse.ArgumentParser(description="The autoresearch keep-or-discard loop, applied to the vault.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("start", help="creates experiment/<tag> from main and measures the baseline twice")
    i.add_argument("tag")
    i.add_argument("--model", default=DEFAULT_CONFIG["model"])
    i.add_argument("--effort", default=DEFAULT_CONFIG["effort"])
    i.add_argument("--budget-usd", type=float, default=DEFAULT_CONFIG["budget_usd"])
    m = sub.add_parser("measure", help="measures the last commit and decides: keep, discard, crash or off-surface")
    m.add_argument("description")
    r = sub.add_parser("report")
    r.add_argument("tag", nargs="?")
    for p in (i, m):
        p.add_argument("--parallel", type=int, default=4)
    a = ap.parse_args()
    root = find_root()
    if a.cmd == "start":
        start(root, a.tag, {"model": a.model, "effort": a.effort, "budget_usd": a.budget_usd}, a.parallel)
    elif a.cmd == "measure":
        measure(root, a.description, a.parallel)
    else:
        tag = a.tag or git(root, "branch", "--show-current").removeprefix("experiment/")
        report(root, tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
