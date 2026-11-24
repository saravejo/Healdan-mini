#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def find_root(start):
    for d in [start, *start.parents]:
        if (d / "CLAUDE.md").is_file() and (d / "2 - Wiki").is_dir():
            return d
    return None


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    if not tool.startswith("mcp__") or "tool_response" not in data:
        return 0
    root = find_root(Path(data.get("cwd") or ".").resolve())
    if root is None:
        return 0
    server = (data.get("mcp_server") or {}).get("name") or tool.split("__")[1]
    response = data["tool_response"]
    body = json.dumps(response, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    folder = root / "0 - Inbox/mcp" / re.sub(r"[^\w.-]+", "-", server)
    if any(folder.glob(f"*_{digest}.json")):
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now():%Y-%m-%dT%H%M%S}_{re.sub(r'[^\w.-]+', '-', tool.split('__')[-1])}_{digest}.json"
    capture = {
        "server": server,
        "tool": tool,
        "input": data.get("tool_input"),
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "session": data.get("session_id"),
        "tool_use_id": data.get("tool_use_id"),
        "response": response,
    }
    (folder / name).write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
