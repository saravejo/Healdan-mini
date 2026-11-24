#!/usr/bin/env bash
set -euo pipefail
gist="$(cd "$(dirname "$0")" && pwd)"
vault="${1:?usage: bash install.sh <vault-folder> [<origin.git>]}"
name="$(basename "$vault")"
origin="${2:-$HOME/Git/$name.git}"

python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "needs python3 >= 3.11 (the stack uses 3.14)" >&2; exit 1; }
if [[ -f "$gist/SHA256SUMS" && "${KIT_EDITED:-0}" != 1 ]]; then
  if command -v shasum >/dev/null; then sum=(shasum -a 256); else sum=(sha256sum); fi
  (cd "$gist" && "${sum[@]}" -c --quiet SHA256SUMS) || {
    echo "the kit does not match SHA256SUMS: download it again; if you edited it on purpose, run with KIT_EDITED=1" >&2
    exit 1
  }
fi
mkdir -p "$vault" && cd "$vault"

folders=(
  "0 - Inbox/mcp" "1 - Projects/vault" "1 - Projects/_unassigned/activities"
  "2 - Wiki/sources" "2 - Wiki/claims" "2 - Wiki/entities" "2 - Wiki/concepts"
  "2 - Wiki/questions" "2 - Wiki/lessons" "2 - Wiki/ideas"
  "3 - Resources/templates" "3 - Resources/evals/results" "3 - Resources/agents/evaluations"
  "4 - Archives/raw/sources" "4 - Archives/raw/meetings" "4 - Archives/raw/sessions" "4 - Archives/raw/assets"
  "4 - Archives/sessions" "4 - Archives/projects"
)
for p in "${folders[@]}"; do mkdir -p "$p" && touch "$p/.gitkeep"; done
mkdir -p .claude/scripts .claude/hooks .claude/skills .claude/agents .claude/rules

cp "$gist"/{validate_vault,new_id,register_source,measure_agent,evaluate_agent,eval_skills,facts,new_note,check_items,experiment}.py \
   "$gist"/pr.sh "$gist"/pre-commit "$gist"/pre-receive .claude/scripts/
cp "$gist"/{guard,archive_session,capture_mcp}.py .claude/hooks/
chmod +x .claude/scripts/* .claude/hooks/*

[[ -f CLAUDE.md ]] || cp "$gist/CLAUDE.md" CLAUDE.md
[[ -f .claude/settings.json ]] || cp "$gist/settings.json" .claude/settings.json
python3 - .claude/settings.json <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
if "autoMemoryEnabled" not in data:
    data["autoMemoryEnabled"] = False
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print('settings.json: added "autoMemoryEnabled": false')
PY
[[ -f .claude/ingestion.toml ]] || cp "$gist/ingestion.toml" .claude/ingestion.toml
[[ -f "3 - Resources/evals/questions.toml" ]] || cp "$gist/questions.toml" "3 - Resources/evals/questions.toml"
[[ -f "3 - Resources/evals/lint.toml" ]] || cp "$gist/lint.toml" "3 - Resources/evals/lint.toml"
python3 .claude/scripts/new_note.py --extract-templates "$gist/templates.md" | tail -1
python3 .claude/scripts/new_note.py --extract-templates "$gist/skill-evals.md" | tail -1 | sed 's/^templates:/skill evals:/'
[[ -f index.md ]] || printf '# Index\n\n## Sources\n\n## Claims\n\n## Entities\n\n## Concepts\n\n## Questions\n\n## Lessons\n\n## Ideas\n' > index.md
[[ -f log.md ]] || printf '# Log\n' > log.md
[[ -f .gitattributes ]] || printf 'log.md merge=union\nindex.md merge=union\n*.jsonl -diff\n' > .gitattributes
[[ -f .gitignore ]] || printf '.obsidian/workspace*.json\n.obsidian/cache\n.trash/\n.claude/worktrees/\n.claude/settings.local.json\n.DS_Store\n__pycache__/\n' > .gitignore

[[ -d .git ]] || git init -q -b main
cp .claude/scripts/pre-commit "$(git rev-parse --git-path hooks)/pre-commit"
chmod +x "$(git rev-parse --git-path hooks)/pre-commit"

if [[ ! -d "$origin" ]]; then
  git init -q --bare -b main "$origin"
  git -C "$origin" config receive.denyNonFastForwards true
  git -C "$origin" config receive.denyDeletes true
fi
cp .claude/scripts/pre-receive "$origin/hooks/pre-receive"
chmod +x "$origin/hooks/pre-receive"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$origin"

python3 .claude/scripts/validate_vault.py
if ! git rev-parse -q --verify HEAD >/dev/null; then
  git add -A
  git commit -q -m "initial vault structure"
  git push -q -u origin main
fi

if ! python3 -c 'import json,os,sys; p=os.path.expanduser("~/.claude/settings.json"); sys.exit(json.load(open(p)).get("cleanupPeriodDays",30) < 36500 if os.path.exists(p) else 1)'; then
  echo "WARNING: also put \"cleanupPeriodDays\": 36500 in ~/.claude/settings.json (the Claude Code sweep applies to the whole machine)." >&2
fi
echo "vault at $(pwd); origin at $origin"
