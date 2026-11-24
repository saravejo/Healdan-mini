#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tomllib
import unicodedata
from datetime import date
from pathlib import Path

from new_id import append_to_index, find_root, next_id

INBOX = "0 - Inbox"
MAP = ".claude/ingestion.toml"


def slug(text):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()[:60] or "source"


def already_registered(root, sha, ref):
    for note in (root / "2 - Wiki/sources").glob("S*.md"):
        text = note.read_text(encoding="utf-8")
        if re.search(rf"^sha256: {sha}$", text, re.M):
            return note, "identical content"
        if ref and re.search(rf'^ref: "?{re.escape(ref)}"?$', text, re.M):
            return note, f"same ref {ref}"
    return None, None


def origin_matches(rule, origin):
    if rule in (None, origin):
        return True
    kind, _, name = rule.partition(":")
    return kind == "mcp" and origin.startswith("mcp:") and name.casefold() in origin.casefold()


def suggested_project(root, origin, content):
    mapping = root / MAP
    if not mapping.is_file():
        return "", ""
    text = content.decode("utf-8", errors="ignore").casefold()
    for rule in tomllib.loads(mapping.read_text(encoding="utf-8")).get("map", []):
        if origin_matches(rule.get("origin"), origin) and rule["value"].casefold() in text:
            return rule["project"], f"{rule.get('origin', '*')} {rule.get('key', '')}={rule['value']}".strip()
    return "", ""


def main():
    ap = argparse.ArgumentParser(description="Single entry point into raw/: moves from the inbox, numbers, locks and creates the S note.")
    ap.add_argument("file")
    ap.add_argument("title")
    ap.add_argument("--url", default="")
    ap.add_argument("--ref", default="", help="stable key in the source tool: permalink, message-id, meeting id")
    a = ap.parse_args()

    root = find_root()
    source = Path(a.file).resolve()
    inbox = (root / INBOX).resolve()
    if inbox not in source.parents or not source.is_file():
        sys.exit(f"the source must be a file inside '{INBOX}/': {a.file}")
    parts = source.relative_to(inbox).parts
    origin_type = f"mcp:{parts[1]}" if len(parts) > 2 and parts[0] == "mcp" else "document"

    content = source.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    existing, reason = already_registered(root, sha, a.ref)
    if existing:
        print(f"already registered ({reason}): {existing.relative_to(root)}. Nothing was changed.")
        return 0

    sid = next_id("S", root)
    meeting = "granola" in origin_type.casefold() or source.suffix.lower() in {".vtt", ".srt"}
    destination = root / "4 - Archives/raw" / ("meetings" if meeting else "sources") / f"{sid}{source.suffix.lower()}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(source, destination)
    os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    project, rule = suggested_project(root, origin_type, content)
    today = date.today().isoformat()
    title = a.title.replace('"', "'")
    note = root / "2 - Wiki/sources" / f"{sid} - {slug(a.title)}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        f'---\nid: {sid}\ntype: source\ntitle: "{title}"\nstatus: current\n'
        f'file: "{destination.relative_to(root).as_posix()}"\nsha256: {sha}\n'
        f'raw_origin: {origin_type}\nref: "{a.ref}"\nurl: {a.url}\n'
        f'suggested_project: {project}\nrouting_rule: "{rule}"\n'
        f"created: {today}\nupdated: {today}\ntags: []\n---\n"
        "> Summary: {{pending}}\n\n## Key points\n{{pending}}\n\n## Routing\n{{pending}}\n",
        encoding="utf-8",
    )
    append_to_index(root, "source", note.stem, sid, title)
    with (root / "log.md").open("a", encoding="utf-8") as log:
        log.write(f"\n## [{today}] register | {sid} | {title}\n")
    print(json.dumps({"id": sid, "raw": destination.relative_to(root).as_posix(), "note": note.relative_to(root).as_posix(),
                      "origin": origin_type, "suggested_project": project, "rule": rule}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
