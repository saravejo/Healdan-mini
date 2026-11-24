#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import tomllib
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path

RAW = "4 - Archives/raw/"
OUTSIDE = ("0 - Inbox/", "3 - Resources/", RAW, ".")
SPECIAL = {"CLAUDE.md", "index.md", "log.md"}
TYPES = {
    "S": ("source", {"current", "archived"}),
    "F": ("claim", {"draft", "current", "superseded", "archived"}),
    "E": ("entity", {"draft", "current", "archived"}),
    "C": ("concept", {"draft", "current", "archived"}),
    "D": ("decision", {"proposed", "current", "replaced", "archived"}),
    "L": ("lesson", {"current", "became-rule", "archived"}),
    "Q": ("question", {"open", "closed", "archived"}),
    "I": ("idea", {"seed", "mature", "adopted", "archived"}),
    "A": ("activity", {"open", "in-progress", "blocked", "done", "cancelled"}),
    "IN": ("infra", {"proposed", "done", "discarded"}),
    "LS": ("session", {"open", "closed"}),
}
PREFIXES = "LS|IN|[SFECDLQIA]"
ID_RE = re.compile(rf"^({PREFIXES})(\d{{4,}})$")
PREFIX_RE = re.compile(rf"^({PREFIXES})\d{{4,}}")
ID_IN_TEXT_RE = re.compile(rf"(?<![\w-])(?:{PREFIXES})\d{{4,}}(?!\w)")
REQUIRED = ("id", "type", "title", "status", "created", "updated")
EXTRAS = {"claim": ("sources", "excerpt"), "activity": ("project", "origin")}
REFERENCES = ("sources", "superseded_by", "related", "origin", "outcomes")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK_RE = re.compile(r"\[\[([^\]|#^]+)")
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
LOG_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (register|ingest|query|lint|decision|infra|session) \| ")
TEXTUAL = {".md", ".txt", ".csv", ".html", ".htm", ".json", ".jsonl", ".vtt", ".srt", ".eml"}
PENDING = "{{pending}}"
DEFAULT_RULES = "3 - Resources/evals/lint.toml"
SKILLS = ".claude/skills"
SKILL_EVALS = "3 - Resources/evals/skills"
FOCUSES = ("safety", "quality")
CHECKS = {
    "protected_intact": ("safety", ()),
    "main_intact": ("safety", ()),
    "zero_invented_ids": ("safety", ()),
    "no_write_outside": ("safety", ("allowed",)),
    "forbidden_tool": ("safety", ("pattern",)),
    "run_ok": ("quality", ()),
    "validator_ok": ("quality", ()),
    "tool_used": ("quality", ("pattern",)),
    "new_files": ("quality", ("files",)),
    "contains": ("quality", ("files", "pattern")),
    "not_contains": ("quality", ("files", "pattern")),
    "answer_contains": ("quality", ("pattern",)),
    "answer_not_contains": ("quality", ("pattern",)),
    "commit_message": ("quality", ("pattern",)),
    "log_contains": ("quality", ("pattern",)),
    "max_cost": ("quality", ("value",)),
}
IMPLICIT = ("protected_intact", "main_intact", "zero_invented_ids", "run_ok")
DEFAULT_REPETITIONS = 3


def find_root(start):
    for d in [start, *start.parents]:
        if (d / "CLAUDE.md").is_file() and (d / "2 - Wiki").is_dir():
            return d
    return Path(__file__).resolve().parents[2]


def frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fields = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if not value.startswith(('"', "'")):
            value = value.split(" #")[0].strip()
        if value.startswith("[") and value.endswith("]"):
            fields[key.strip()] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            fields[key.strip()] = value.strip("\"'")
    return fields, text[end + 4:]


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def strings_of(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_of(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_of(v)


@lru_cache(maxsize=256)
def raw_text(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".json":
        try:
            text = "\n".join(strings_of(json.loads(text)))
        except json.JSONDecodeError:
            pass
    elif p.suffix == ".jsonl":
        parts = []
        for line in text.splitlines():
            try:
                parts.extend(strings_of(json.loads(line)))
            except json.JSONDecodeError:
                parts.append(line)
        text = "\n".join(parts)
    return normalize(text)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files(root):
    for p in root.rglob("*"):
        parts = p.relative_to(root).parts
        if p.is_file() and not any(part.startswith(".") for part in parts):
            yield p, "/".join(parts)


def notes(root):
    for p, rel in files(root):
        if p.suffix == ".md" and p.name not in SPECIAL and not rel.startswith(OUTSIDE):
            yield p, rel


def link_targets(root):
    targets = set()
    for p, rel in files(root):
        targets.update({p.name, rel})
        if p.suffix == ".md":
            targets.update({p.stem, rel[:-3]})
    return targets


def ids_by_name(root):
    return {m.group(0): rel for p, rel in notes(root) if (m := PREFIX_RE.match(p.name))}


def load_rules(path):
    if not path or not Path(path).is_file():
        return []
    rules = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("rule", [])
    return [{**r, "re": re.compile(r["pattern"], re.M)} for r in rules]


class Context:
    def __init__(self, root, rules, expensive=None):
        self.root = root
        self.rules = rules
        self.expensive = expensive
        self.ids = ids_by_name(root)
        self.targets = link_targets(root)
        self.source_file = {}

    def check_expensive(self, rel):
        return self.expensive is None or rel in self.expensive


def verify(p, rel, ctx, complete):
    errors, warnings = [], []
    text = p.read_text(encoding="utf-8")
    fields, body = frontmatter(text)
    if fields is None or "id" not in fields:
        return ([f"{rel}: wiki note without frontmatter with an id"] if rel.startswith("2 - Wiki/") else []), [], None, None
    nid = fields["id"]
    m = ID_RE.match(nid)
    if not m:
        return [f"{rel}: invalid id '{nid}' (prefix + at least 4 digits)"], [], None, None
    if f"{int(m.group(2)):04d}" != m.group(2):
        return [f"{rel}: id {nid} not in canonical form (leading zeros only up to 4 digits)"], [], None, None
    note_type, valid_statuses = TYPES[m.group(1)]
    errors += [f"{rel}: required field empty: {c}" for c in REQUIRED + EXTRAS.get(note_type, ()) if not fields.get(c)]
    if fields.get("type") and fields["type"] != note_type:
        errors.append(f"{rel}: type '{fields['type']}' does not match prefix {m.group(1)} ({note_type})")
    if not (pm := PREFIX_RE.match(p.name)) or pm.group(0) != nid:
        errors.append(f"{rel}: file name must start with the id {nid}")
    status = fields.get("status")
    if status and status not in valid_statuses:
        errors.append(f"{rel}: status '{status}' invalid for {note_type}: {sorted(valid_statuses)}")
    if status in ("superseded", "replaced") and not fields.get("superseded_by"):
        errors.append(f"{rel}: status {status} requires superseded_by")
    if note_type == "idea" and status == "adopted" and not fields.get("outcomes"):
        errors.append(f"{rel}: adopted idea requires outcomes (what it became: A, D, IN or project)")
    for key in ("created", "updated", "due", "completed_on"):
        if fields.get(key) and not DATE_RE.match(fields[key]):
            errors.append(f"{rel}: {key} must be YYYY-MM-DD, got '{fields[key]}'")
    if note_type == "activity":
        if status == "done" and not fields.get("completed_on"):
            errors.append(f"{rel}: done activity requires completed_on")
        project = fields.get("project")
        if project and not any((ctx.root / folder / project).is_dir() for folder in ("1 - Projects", "4 - Archives/projects")):
            errors.append(f"{rel}: project '{project}' does not exist in 1 - Projects/ or in 4 - Archives/projects/")
    for key in REFERENCES:
        value = fields.get(key) or []
        for ref in [value] if isinstance(value, str) else value:
            if not ID_RE.match(ref):
                errors.append(f"{rel}: {key} contains '{ref}', which is not an id")
            elif ref not in ctx.ids:
                errors.append(f"{rel}: {key} points to {ref}, which does not exist")
            elif key == "sources" and not ref.startswith("S"):
                errors.append(f"{rel}: sources only accepts S ids, got {ref}")
    if "> Summary:" not in body[:600]:
        errors.append(f"{rel}: missing the '> Summary:' line right after the frontmatter")
    if note_type == "source":
        raw = ctx.root / fields.get("file", "")
        if not fields.get("file") or not raw.is_file():
            errors.append(f"{rel}: raw file missing: {fields.get('file')}")
        elif ctx.check_expensive(rel) or ctx.check_expensive(fields["file"]):
            if sha256(raw) != fields.get("sha256"):
                errors.append(f"{rel}: sha256 does not match: {fields['file']} was altered")
    if fields.get("excerpt") and ctx.check_expensive(rel):
        errors += check_excerpt(rel, fields, ctx)
    without_code = CODE_RE.sub("", body)
    for target in LINK_RE.findall(without_code):
        if target.strip() not in ctx.targets:
            errors.append(f"{rel}: broken link [[{target.strip()}]]")
    for cited in sorted(set(ID_IN_TEXT_RE.findall(without_code)) - ctx.ids.keys()):
        errors.append(f"{rel}: cites {cited}, which does not exist (invented ID?). If it is not an id, put it in backticks")
    for rule in ctx.rules:
        if fnmatch(rel, rule.get("where", "*")) and (match := rule["re"].search(body)):
            msg = f"{rel}: [{rule['id']}] {rule['message']} (found: '{match.group(0)[:40]}')"
            (errors if rule.get("level") == "error" else warnings).append(msg)
    if complete and PENDING in text:
        errors.append(f"{rel}: still has {PENDING}")
    return errors, warnings, nid, fields


def check_excerpt(rel, fields, ctx):
    excerpt = normalize(fields["excerpt"])
    sources = fields.get("sources") or []
    textual = []
    for sid in sources if isinstance(sources, list) else [sources]:
        path = ctx.source_file.get(sid)
        if path is None and sid in ctx.ids:
            f, _ = frontmatter((ctx.root / ctx.ids[sid]).read_text(encoding="utf-8"))
            path = ctx.source_file[sid] = (ctx.root / f.get("file", "")) if f else None
        if path and path.is_file() and path.suffix.lower() in TEXTUAL:
            textual.append(path)
    if textual and not any(excerpt in raw_text(str(c)) for c in textual):
        return [f"{rel}: the quoted excerpt does not appear literally in any textual source of {sources} (hallucination or paraphrase)"]
    return []


def verify_all(root, rules, expensive=None):
    ctx = Context(root, rules, expensive)
    listing = list(notes(root))
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda nr: verify(nr[0], nr[1], ctx, True), listing))
    errors, warnings, seen, citers = [], [], {}, {}
    index = (root / "index.md").read_text(encoding="utf-8") if (root / "index.md").is_file() else ""
    for (p, rel), (e, w, nid, fields) in zip(listing, results):
        errors += e
        warnings += w
        cited = set(ID_IN_TEXT_RE.findall(CODE_RE.sub("", frontmatter(p.read_text(encoding="utf-8"))[1])))
        for key in REFERENCES if fields else ():
            value = fields.get(key) or []
            cited |= {value} if isinstance(value, str) else set(value)
        for c in cited - {nid}:
            citers.setdefault(c, set()).add(rel)
        if nid:
            if nid in seen:
                errors.append(f"{rel}: duplicate id {nid} (also in {seen[nid]})")
            seen[nid] = rel
            if rel.startswith("2 - Wiki/"):
                n = len(re.findall(rf"\[\[{nid}(?!\d)", index))
                if n == 0:
                    errors.append(f"index.md: missing {nid}")
                elif n > 1:
                    errors.append(f"index.md: {nid} appears {n} times")
    for nid, rel in seen.items():
        if rel.startswith("2 - Wiki/") and not citers.get(nid):
            warnings.append(f"{rel}: orphan (no other note cites {nid})")
    for target in LINK_RE.findall(index):
        if target.strip() not in ctx.targets:
            errors.append(f"index.md: broken link [[{target.strip()}]]")
    if (root / "log.md").is_file():
        for i, line in enumerate((root / "log.md").read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("## ") and not LOG_RE.match(line):
                errors.append(f"log.md:{i}: header out of format: {line}")
    pending = [p for p in (root / "0 - Inbox").rglob("*") if p.is_file() and not p.name.startswith(".")]
    if pending:
        warnings.append(f"0 - Inbox/: {len(pending)} file(s) waiting for ingestion or triage")
    e, w = verify_configuration(root)
    return errors + e, warnings + w


def verify_eval(path, name):
    rel = f"{SKILL_EVALS}/{path.name}"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return [f"{rel}: invalid TOML: {error}"]
    errors = []
    if data.get("skill") != name:
        errors.append(f"{rel}: declare skill = \"{name}\"")
    repetitions = data.get("repetitions", DEFAULT_REPETITIONS)
    if not isinstance(repetitions, int) or repetitions < 2:
        errors.append(f"{rel}: repetitions must be an integer >= 2 (predictability compares the repetitions)")
    for key in ("min_quality", "min_predictability"):
        value = data.get(key)
        if value is not None and not (isinstance(value, (int, float)) and 0 < value <= 1):
            errors.append(f"{rel}: {key} must be between 0 and 1")
    cases = data.get("case", [])
    for focus in FOCUSES:
        if not any(c.get("focus") == focus for c in cases):
            errors.append(f"{rel}: missing at least one case with focus = \"{focus}\"")
    seen = set()
    for case in cases:
        cid = case.get("id") or "?"
        if cid in seen:
            errors.append(f"{rel}: duplicate case {cid}")
        seen.add(cid)
        if case.get("focus") not in FOCUSES:
            errors.append(f"{rel}: case {cid}: focus must be {' or '.join(FOCUSES)}")
        if not str(case.get("prompt", "")).startswith(f"/{name}"):
            errors.append(f"{rel}: case {cid}: the prompt starts with /{name}, as in production")
        checks = case.get("check", [])
        if not checks:
            errors.append(f"{rel}: case {cid}: no check")
        categories = set()
        for ch in checks:
            check_type = ch.get("type")
            if check_type not in CHECKS:
                errors.append(f"{rel}: case {cid}: unknown check '{check_type}': {sorted(CHECKS)}")
                continue
            category = ch.get("category", CHECKS[check_type][0])
            if category not in FOCUSES:
                errors.append(f"{rel}: case {cid}: invalid category '{category}' in {check_type}")
            categories.add(category)
            errors += [f"{rel}: case {cid}: {check_type} requires the field {c}" for c in CHECKS[check_type][1] if c not in ch]
            if "pattern" in ch:
                try:
                    re.compile(ch["pattern"])
                except re.error as error:
                    errors.append(f"{rel}: case {cid}: invalid regex in {check_type}: {error}")
        if checks and case.get("focus") in FOCUSES and case["focus"] not in categories:
            errors.append(f"{rel}: case {cid}: a {case['focus']} case needs at least one check of that category")
    return errors


def verify_configuration(root):
    errors, warnings = [], []
    for name, required in (("settings.json", True), ("settings.local.json", False)):
        path = root / ".claude" / name
        if not path.is_file():
            if required:
                errors.append(f".claude/{name}: missing")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f".claude/{name}: invalid JSON: {error}")
            continue
        value = data.get("autoMemoryEnabled")
        if (required and value is not False) or (not required and value not in (None, False)):
            errors.append(f'.claude/{name}: auto memory stays off: "autoMemoryEnabled": false')
    for agent in sorted((root / ".claude/agents").glob("*.md")):
        fields, _ = frontmatter(agent.read_text(encoding="utf-8"))
        if fields and "memory" in fields:
            errors.append(f".claude/agents/{agent.name}: remove the memory field: a subagent keeps no memory between sessions")
    for folder in (".claude/agent-memory", ".claude/agent-memory-local"):
        if (root / folder).exists():
            warnings.append(f"{folder}/: subagent memory from before; with memory off, it is not read")
    skills = sorted(p.parent.name for p in (root / SKILLS).glob("*/SKILL.md"))
    for name in skills:
        path = root / SKILL_EVALS / f"{name}.toml"
        if path.is_file():
            errors += verify_eval(path, name)
        else:
            errors.append(f"{SKILLS}/{name}: skill without an eval. Missing {SKILL_EVALS}/{name}.toml, with at least one "
                          "safety case and one quality case. The agent does not write in evals/: draft the eval in an IN note")
    for path in sorted((root / SKILL_EVALS).glob("*.toml")):
        if path.stem not in skills:
            warnings.append(f"{SKILL_EVALS}/{path.name}: eval of a skill that does not exist")
    return errors, warnings


def hook_mode(rules_path):
    data = json.load(sys.stdin)
    path = Path(data.get("tool_input", {}).get("file_path", ""))
    if not path.is_file():
        return 0
    root = find_root(path.resolve().parent)
    try:
        rel = path.resolve().relative_to(root).as_posix()
    except ValueError:
        return 0
    if rel.startswith(".claude/") and (rel.endswith("/SKILL.md") or rel.startswith((".claude/agents/", ".claude/settings"))):
        errors, _ = verify_configuration(root)
        if errors:
            print("Vault validator:\n" + "\n".join(errors), file=sys.stderr)
            return 2
        return 0
    if path.suffix != ".md" or path.name in SPECIAL or rel.startswith(OUTSIDE):
        return 0
    rules = load_rules(rules_path or root / DEFAULT_RULES)
    errors, warnings, _, _ = verify(path, rel, Context(root, rules), complete=False)
    if errors:
        print("Vault validator:\n" + "\n".join(errors + warnings), file=sys.stderr)
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook", action="store_true", help="PostToolUse mode: reads the hook JSON from stdin")
    ap.add_argument("--rules", help=f"regex rules file (default: {DEFAULT_RULES})")
    ap.add_argument("--changed", help="list of changed paths ('-' = stdin): hash and excerpt only for them")
    a = ap.parse_args()
    if a.hook:
        return hook_mode(a.rules)
    root = find_root(Path.cwd())
    expensive = None
    if a.changed:
        source = sys.stdin if a.changed == "-" else open(a.changed, encoding="utf-8")
        expensive = {line.strip() for line in source if line.strip()}
    errors, warnings = verify_all(root, load_rules(a.rules or root / DEFAULT_RULES), expensive)
    for warning in warnings:
        print(f"warning: {warning}")
    print("\n".join(errors) if errors else "vault ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
