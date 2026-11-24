#!/usr/bin/env python3
import fcntl
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PREFIXES = {"S", "F", "E", "C", "D", "L", "Q", "I", "A", "IN", "LS"}


def find_root(start=None):
    start = start or Path.cwd()
    for d in [start, *start.parents]:
        if (d / "CLAUDE.md").is_file() and (d / "2 - Wiki").is_dir():
            return d
    sys.exit("run inside the vault (could not find CLAUDE.md + 2 - Wiki/)")


def highest_on_disk(prefix, root):
    pattern = re.compile(rf"^{prefix}(\d{{4,}})")
    highest = 0
    for p in root.rglob(f"{prefix}[0-9][0-9][0-9][0-9]*"):
        if not any(part.startswith(".") for part in p.relative_to(root).parts):
            highest = max(highest, int(pattern.match(p.name).group(1)))
    return highest


def common_dir(root):
    try:
        output = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(output.stdout.strip()) if output.returncode == 0 else None


def next_id(prefix, root):
    highest = highest_on_disk(prefix, root)
    common = common_dir(root)
    if common is None:
        return f"{prefix}{highest + 1:04d}"
    counter = common / "vault-ids.json"
    with open(common / "vault-ids.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reservations = json.loads(counter.read_text()) if counter.is_file() else {}
        n = max(highest, reservations.get(prefix, 0)) + 1
        reservations[prefix] = n
        temporary = counter.with_suffix(".tmp")
        temporary.write_text(json.dumps(reservations, indent=2, sort_keys=True))
        os.replace(temporary, counter)
    return f"{prefix}{n:04d}"


SECTIONS = {"source": "Sources", "claim": "Claims", "entity": "Entities", "concept": "Concepts",
            "question": "Questions", "lesson": "Lessons", "idea": "Ideas"}


def append_to_index(root, note_type, target, nid, title):
    section = SECTIONS.get(note_type)
    if not section:
        return
    index = root / "index.md"
    with open(root / "index.md", "a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        lines = lock.read().splitlines()
        new = f"- [[{target}|{nid}]] {title}"
        header = f"## {section}"
        if header not in lines:
            lines += ["", header]
        end = lines.index(header) + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        while end > 0 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, new)
        if end + 1 < len(lines) and lines[end + 1].startswith("## "):
            lines.insert(end + 1, "")
        lock.seek(0)
        lock.truncate()
        lock.write("\n".join(lines) + "\n")
    return index


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PREFIXES:
        sys.exit("usage: new_id.py " + "|".join(sorted(PREFIXES)))
    print(next_id(sys.argv[1], find_root()))
