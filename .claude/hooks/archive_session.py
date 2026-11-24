#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def encode(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def archive(source, destination, session=None):
    new = 0
    for f in sorted(source.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(source)
        if session and not rel.parts[0].startswith(session):
            continue
        content = f.read_bytes()
        target = destination / rel / f"{hashlib.sha256(content).hexdigest()[:16]}{f.suffix}"
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        os.chmod(target, 0o444)
        new += 1
    return new


def main():
    data = json.load(sys.stdin)
    transcript = Path(data.get("transcript_path") or "")
    if not transcript.parent.is_dir():
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".").resolve()
    destination = root / "4 - Archives/raw/sessions"
    if data.get("hook_event_name") == "SessionEnd":
        new = archive(transcript.parent, destination, data.get("session_id") or "")
    else:
        name = encode(root)
        folders = [d for d in transcript.parent.parent.iterdir()
                   if d.is_dir() and (d.name == name or d.name.startswith(name + "--claude-worktrees-"))]
        new = sum(archive(d, destination) for d in folders)
    if new:
        print(f"archiver: {new} new file(s) in 4 - Archives/raw/sessions/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
