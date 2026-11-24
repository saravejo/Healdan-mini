#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from new_id import find_root
from validate_vault import ID_IN_TEXT_RE, ids_by_name

SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_ids": {"type": "array", "items": {"type": "string"}},
        "knows": {"type": "boolean"},
    },
    "required": ["answer", "cited_ids", "knows"],
})
INSTRUCTION = (
    "Answer only with what is in this vault. Read index.md first. "
    "In cited_ids, list the IDs of the notes that support the answer. "
    "If the vault does not have the answer, say you don't know and set knows=false.\n\nQuestion: "
)
DEFAULT_CONFIG = {"model": "sonnet", "effort": "high", "budget_usd": 0.50}
AVERAGES = ("coverage", "accuracy", "correct_refusal", "cost_usd", "seconds")
SUMS = ("invented_ids",)
QUALITY = ("coverage", "accuracy", "correct_refusal")


def ask(text, root, config):
    cmd = ["claude", "-p", INSTRUCTION + text, "--output-format", "json", "--json-schema", SCHEMA,
           "--allowedTools", "Read,Grep,Glob", "--permission-mode", "dontAsk",
           "--model", config["model"], "--effort", config["effort"], "--max-budget-usd", str(config["budget_usd"])]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"} | {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
    start = time.monotonic()
    output = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=900, env=env)
    seconds = time.monotonic() - start
    try:
        data = json.loads(output.stdout)
    except json.JSONDecodeError:
        return None, 0.0, seconds, (output.stderr or output.stdout)[-500:]
    if not data.get("structured_output"):
        return None, data.get("total_cost_usd", 0.0), seconds, "no structured_output"
    return data["structured_output"], data.get("total_cost_usd", 0.0), seconds, None


def grade(q, r, existing):
    cited = set(r["cited_ids"]) | set(ID_IN_TEXT_RE.findall(r["answer"]))
    result = {"invented_ids": len(cited - existing), "invented": sorted(cited - existing)}
    expected = set(q.get("expected_notes", []))
    if not expected:
        return result | {"correct_refusal": float(not r["knows"])}
    result["coverage"] = len(expected & cited) / len(expected)
    if q.get("facts"):
        result["accuracy"] = sum(f.lower() in r["answer"].lower() for f in q["facts"]) / len(q["facts"])
    return result


def average(items, key):
    values = [i[key] for i in items if i.get(key) is not None]
    return round(sum(values) / len(values), 4) if values else None


def overall_score(summary):
    values = [summary[k] for k in QUALITY if summary.get(k) is not None]
    return round(sum(values) / len(values), 4) if values else None


def run(root, config=None, ids=None, parallel=4):
    config = {**DEFAULT_CONFIG, **(config or {})}
    folder = root / "3 - Resources/evals"
    questions = tomllib.loads((folder / "questions.toml").read_text(encoding="utf-8"))["question"]
    if ids:
        questions = [q for q in questions if q["id"] in ids]
    existing = set(ids_by_name(root))

    def one(q):
        r, cost, seconds, error = ask(q["text"], root, config)
        item = {"id": q["id"], "cost_usd": cost, "seconds": round(seconds, 1)}
        if r is None:
            return item | {"error": error}
        return item | grade(q, r, existing) | {"cited_ids": r["cited_ids"], "answer": r["answer"]}

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        items = list(pool.map(one, questions))
    summary = {k: average(items, k) for k in AVERAGES} | {k: sum(i.get(k, 0) for i in items) for k in SUMS}
    summary |= {"score": overall_score(summary), "errors": sum(1 for i in items if "error" in i), "questions": len(items), "config": config}
    results = folder / "results"
    results.mkdir(exist_ok=True)
    destination = results / f"{datetime.now():%Y-%m-%dT%H%M%S%f}.json"
    destination.write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary, items, destination


def main():
    ap = argparse.ArgumentParser(description="Layer 2 against hallucination and accuracy yardstick: runs the test questions.")
    ap.add_argument("--ids", nargs="*", help="run only these questions")
    ap.add_argument("--parallel", type=int, default=4, help="simultaneous questions")
    ap.add_argument("--tolerance", type=float, default=0.05)
    ap.add_argument("--model", default=DEFAULT_CONFIG["model"])
    ap.add_argument("--effort", default=DEFAULT_CONFIG["effort"])
    ap.add_argument("--budget-usd", type=float, default=DEFAULT_CONFIG["budget_usd"], help="spending cap per question")
    a = ap.parse_args()

    root = find_root()
    previous_runs = sorted((root / "3 - Resources/evals/results").glob("*.json"))
    config = {"model": a.model, "effort": a.effort, "budget_usd": a.budget_usd}
    summary, items, destination = run(root, config, a.ids, a.parallel)
    for item in items:
        details = ", ".join(f"{k}={item[k]}" for k in AVERAGES + SUMS if k in item)
        print(f"{item['id']}: {details}" + (f" ERROR {item['error']}" if "error" in item else "")
              + (f" INVENTED {item['invented']}" if item.get("invented") else ""))

    previous = {}
    if previous_runs and not a.ids:
        candidate = json.loads(previous_runs[-1].read_text(encoding="utf-8"))["summary"]
        previous = candidate if candidate.get("config") == summary["config"] else {}
        if not previous:
            print("\nthe previous run used a different configuration (model, effort or budget): no comparison.")
    failed = summary["invented_ids"] > 0 or summary["errors"] > 0
    print(f"\nconfig: {summary['config']}\nmetric            current  previous")
    for k in ("score",) + AVERAGES + SUMS:
        before, now = previous.get(k), summary[k]
        print(f"{k:<16} {now!s:>7} {before!s:>9}")
        if k in QUALITY + ("score",) and None not in (before, now) and now < before - a.tolerance:
            failed = True
    if summary["invented_ids"]:
        print("\nInvented IDs > 0: the baseline is zero, so this is a regression.")
    print(f"\nresult saved to {destination.relative_to(root)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
