#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from new_id import find_root
from validate_vault import TEXTUAL, frontmatter, ids_by_name, normalize, raw_text

TYPES = {"F", "E", "C", "D", "L", "Q", "I", "A", "IN", "none"}
LITERAL_FIELDS = ("owner", "due_excerpt")


def check(item, default_source, root, ids):
    item_type = item.get("type")
    if item_type not in TYPES:
        return "invalid", f"type '{item_type}' does not exist"
    if item_type == "none":
        return "ignored", "routed as noise"
    source = item.get("source") or default_source
    if not source or source not in ids or not source.startswith("S"):
        return "hallucination", f"source '{source}' does not exist in the vault"
    if not (item.get("excerpt") or "").strip():
        return "unsupported", "item without an excerpt from the raw source"
    fields, _ = frontmatter((root / ids[source]).read_text(encoding="utf-8"))
    raw = root / (fields or {}).get("file", "")
    if not raw.is_file() or raw.suffix.lower() not in TEXTUAL:
        return "unverifiable", f"raw file of {source} is not textual: check it by hand"
    text = raw_text(str(raw))
    if normalize(item["excerpt"]) not in text:
        return "hallucination", "excerpt does not appear in the raw source"
    for field in LITERAL_FIELDS:
        if item.get(field) and normalize(item[field]) not in text:
            return "hallucination", f"{field} '{item[field]}' does not appear in the raw source"
    if item.get("due") and not item.get("due_excerpt"):
        return "unsupported", "due without due_excerpt (the raw-source expression it came from)"
    return "supported", ""


def main():
    ap = argparse.ArgumentParser(description="Checks, without an LLM, an extractor subagent's delivery against the raw source.")
    ap.add_argument("items", help="JSON: {\"source\": \"S0001\", \"items\": [...]} or a list of items ('-' = stdin)")
    ap.add_argument("--session", default="<LS>", help="LS id, only to build the self-assessment command")
    a = ap.parse_args()

    root = find_root()
    data = json.load(sys.stdin if a.items == "-" else open(a.items, encoding="utf-8"))
    default_source = data.get("source") if isinstance(data, dict) else None
    items = data.get("items", []) if isinstance(data, dict) else data
    ids = ids_by_name(root)

    count = {}
    for n, item in enumerate(items, 1):
        verdict, reason = check(item, default_source, root, ids)
        count[verdict] = count.get(verdict, 0) + 1
        summary = (item.get("text") or item.get("excerpt") or "")[:70]
        print(f"{n:>3} {item.get('type', '?'):<4} {verdict:<16} {summary}" + (f"  [{reason}]" if reason else ""))

    checked = sum(v for k, v in count.items() if k not in ("ignored", "invalid"))
    print("\n" + json.dumps({"checked": checked, **count}, ensure_ascii=False))
    print(f"\nself-assessment: python3 .claude/scripts/evaluate_agent.py record --session {a.session} "
          f"--checked {checked} --unsupported {count.get('unsupported', 0)} "
          f"--hallucinations-session {count.get('hallucination', 0)}")
    return 1 if count.get("hallucination") or count.get("unsupported") or count.get("invalid") else 0


if __name__ == "__main__":
    sys.exit(main())
