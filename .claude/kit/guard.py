#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PROTECTED = {
    "4 - Archives/raw/": "raw/ is immutable. A new source enters only through "
    "`python3 .claude/scripts/register_source.py \"0 - Inbox/<file>\" \"<title>\"`. "
    "To read, use Read.",
    "3 - Resources/evals/": "The test-question set is the measurement yardstick: the agent does not change it. "
    "Propose the change in an I note.",
    "0 - Inbox/mcp/": "MCP captures are written only by the capture_mcp.py hook, with the tool's response "
    "unedited. To register one, use register_source.py.",
    "3 - Resources/agents/": "Session evaluations are recorded only by `python3 .claude/scripts/evaluate_agent.py record`, "
    "and are never edited.",
    "/.claude/projects/": "The original Claude Code transcripts are never deleted or edited: "
    "the archiver copies them to 4 - Archives/raw/sessions/.",
}
MUTATORS = {"rm", "rmdir", "mv", "unlink", "truncate", "chmod", "chflags", "touch", "tee", "dd"}
DESTINATION_ONLY = {"cp", "ln", "install", "rsync"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
WRAPPERS = {"sudo", "command", "nohup", "time", "env", "xargs", "builtin"}
GIT_REMOTE_OK = {"push", "fetch", "pull", "ls-remote", "request-pull"}


def protected(text):
    target = text if text.endswith("/") else text + "/"
    for fragment, reason in PROTECTED.items():
        if fragment in target:
            return reason
    return None


def local_origin(cwd):
    try:
        url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    path = Path(url).expanduser()
    return str(path.resolve()) if url and path.is_dir() else None


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    current = []
    for token in lexer:
        if token in SEPARATORS:
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def check_git(args, origin):
    sub = next((a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] not in ("-C", "-c"))), "")
    if any("hooksPath" in a for a in args):
        return "Do not change core.hooksPath: the pre-commit is one of the vault's barriers."
    if sub == "commit" and any(a == "--no-verify" or re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in args):
        return "Committing without the pre-commit is not allowed: fix what the validator pointed out."
    if sub == "push":
        positionals = [a for a in args[args.index("push") + 1:] if not a.startswith("-")]
        if len(positionals) < 2 or any(a in ("--all", "--mirror") for a in args) or any(
            re.search(r"(^|:|refs/heads/)main$", a) for a in positionals[1:]
        ):
            return "Pushing to main is accepting a PR, and that is the human's job. Push only the session branch: `git push origin session/LSxxxx`."
    if origin and any(origin in os.path.expanduser(a) for a in args) and sub not in GIT_REMOTE_OK:
        return "The origin holds the vault's state of record: the agent does not change it."
    return None


def check_bash(command, origin):
    try:
        parts = list(segments(command))
    except ValueError:
        return protected(command) and "Unparseable command that mentions a protected folder."
    inside = None
    for tokens in parts:
        for i, t in enumerate(tokens[:-1]):
            if t in (">", ">>"):
                target = tokens[i + 1]
                if reason := protected(target) or (inside if not target.startswith("/") else None):
                    return reason
        while len(tokens) > 1 and tokens[0] in WRAPPERS:
            tokens = tokens[1:]
        cmd, args = tokens[0], [t for t in tokens[1:] if t not in (">", ">>", "<")]
        if any(t.endswith("pr.sh") for t in tokens) and "accept" in args:
            return "Accepting a PR is the human's job (`pr.sh accept`). The agent may run `pr.sh open`."
        if any(t.endswith("evaluate_agent.py") for t in tokens) and "human-review" in args:
            return "The human review is recorded by the human. Record your self-assessment with --origin self-assessment."
        if cmd == "claude" and "purge" in args:
            return "Nothing is deleted: `claude purge` would remove the project's transcripts and memory."
        if cmd == "cd":
            inside = protected(args[0]) if args else None
            continue
        if cmd == "git":
            if reason := check_git(args, origin):
                return reason
            continue
        if origin and any(origin in os.path.expanduser(t) for t in args):
            return "The origin holds the vault's state of record: the agent does not change it."
        mutating = (
            cmd in MUTATORS
            or (cmd in ("sed", "perl") and any(t.startswith("-i") or t == "--in-place" for t in args))
            or (cmd == "find" and any(t in ("-delete", "-exec", "-execdir") for t in args))
        )
        if mutating and (reason := next(filter(None, map(protected, args)), None) or inside):
            return reason
        if cmd in DESTINATION_ONLY and args and (reason := protected(args[-1]) or inside):
            return reason
    return None


def main():
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    origin = local_origin(data.get("cwd") or ".")
    if data.get("tool_name") == "Bash":
        reason = check_bash(tool_input.get("command", ""), origin)
    else:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        reason = protected(path) or (
            "The origin holds the vault's state of record: the agent does not change it."
            if origin and str(Path(path).expanduser().resolve()).startswith(origin) else None
        )
    if reason:
        print(f"Blocked by the guard hook: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
