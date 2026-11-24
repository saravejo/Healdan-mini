#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from new_id import append_to_index, find_root, next_id
from register_source import slug

TEMPLATES = "3 - Resources/templates"
TYPES = {
    "claim": ("F", "2 - Wiki/claims"),
    "entity": ("E", "2 - Wiki/entities"),
    "concept": ("C", "2 - Wiki/concepts"),
    "decision": ("D", "1 - Projects/{project}"),
    "lesson": ("L", "2 - Wiki/lessons"),
    "question": ("Q", "2 - Wiki/questions"),
    "idea": ("I", "2 - Wiki/ideas"),
    "activity": ("A", "1 - Projects/{project}/activities"),
    "infra": ("IN", "1 - Projects/vault"),
    "session": ("LS", "4 - Archives/sessions"),
}
FILE_RE = re.compile(r"^### `([^`]+)`\n\n````[a-z]*\n(.*?)\n````$", re.M | re.S)


def format_value(value):
    if value.startswith("[") or re.fullmatch(r"[\w./@-]*", value):
        return value
    return f'"{value}"' if "'" in value else f"'{value}'"


def apply_fields(text, fields):
    end = text.find("\n---", 3)
    head, rest = text[:end], text[end:]
    for key, value in fields.items():
        line = f"{key}: {format_value(value)}"
        head, n = re.subn(rf"^{re.escape(key)}:.*$", lambda _: line, head, count=1, flags=re.M)
        if not n:
            head += "\n" + line
    return head + rest


def create(root, note_type, title, project, fields):
    if note_type == "source":
        sys.exit("a new source enters only through register_source.py")
    prefix, folder = TYPES[note_type]
    if "{project}" in folder:
        if not project and note_type == "decision":
            sys.exit("a decision needs --project")
        folder = folder.format(project=project or "_unassigned")
        if not (root / folder.split("/activities")[0]).is_dir():
            sys.exit(f"the project does not exist: {folder.split('/activities')[0]}")
    template = root / TEMPLATES / f"{note_type}.md"
    if not template.is_file():
        sys.exit(f"template missing: {template.relative_to(root)}")
    nid = next_id(prefix, root)
    text = (template.read_text(encoding="utf-8")
            .replace("{{id}}", nid).replace("{{title}}", title.replace('"', "'"))
            .replace("{{date}}", date.today().isoformat()).replace("{{project}}", project or "_unassigned"))
    text = apply_fields(text, fields)
    destination = root / folder / f"{nid} - {slug(title)}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "x", encoding="utf-8") as f:
        f.write(text)
    append_to_index(root, note_type, destination.stem, nid, title)
    print(json.dumps({"id": nid, "note": destination.relative_to(root).as_posix()}, ensure_ascii=False))


def extract(root, package, force):
    count = {"created": 0, "kept": 0}
    for path, content in FILE_RE.findall(Path(package).read_text(encoding="utf-8")):
        destination = root / path
        action = "kept" if destination.exists() and not force else "created"
        if action == "created":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content + "\n", encoding="utf-8")
        count[action] += 1
        print(f"{action}: {path}")
    print(f"templates: {count['created']} created, {count['kept']} kept")


def main():
    ap = argparse.ArgumentParser(description="Creates a note from the type's template: id, dates, folder and index without an LLM.")
    ap.add_argument("type", nargs="?", choices=sorted(TYPES))
    ap.add_argument("title", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--field", action="append", default=[], metavar="KEY=VALUE",
                    help="fills a frontmatter field; repeat for several (e.g. --field sources=[S0001])")
    ap.add_argument("--extract-templates", metavar="PACKAGE", help="installs the files of a templates.md package")
    ap.add_argument("--force", action="store_true", help="with --extract-templates, overwrites existing files")
    a = ap.parse_args()
    if a.extract_templates:
        extract(Path.cwd(), a.extract_templates, a.force)
        return 0
    if not a.type or not a.title:
        ap.error("give the type and the title")
    fields = dict(c.split("=", 1) for c in a.field)
    create(find_root(), a.type, a.title, a.project, fields)
    return 0


if __name__ == "__main__":
    sys.exit(main())
