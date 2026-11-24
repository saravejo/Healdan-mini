#!/usr/bin/env bash
set -euo pipefail
action="${1:-}"
branch="${2:-}"
[[ "$action" =~ ^(open|accept)$ && -n "$branch" ]] || { echo "usage: pr.sh open|accept <session-branch>" >&2; exit 2; }
cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
origin_url=$(git remote get-url origin)
append_only=("4 - Archives/raw/" "3 - Resources/agents/evaluations/" "3 - Resources/evals/results/")
git fetch -q origin

check() {
  local forbidden tmp
  forbidden=$(git diff --name-status --no-renames "origin/main...$branch" -- "${append_only[@]}" | grep -v '^A' || true)
  if [[ -n "$forbidden" ]]; then
    echo "the branch changes or removes files in append-only folders:" >&2
    echo "$forbidden" >&2
    return 1
  fi
  yardstick_changed=$(git diff --name-only --no-renames "origin/main...$branch" -- "3 - Resources/evals" ':(exclude)3 - Resources/evals/results')
  if [[ -n "$yardstick_changed" ]]; then
    echo "warning: the branch changes the yardstick; it only takes effect after acceptance, and until then the PR is judged by main's:" >&2
    echo "$yardstick_changed" >&2
  fi
  tmp=$(mktemp -d)
  git diff --name-only --no-renames "origin/main...$branch" > "$tmp/.changed"
  git archive "$branch" -- . ':(exclude)4 - Archives/raw/sessions' | tar -x -C "$tmp"
  git show "origin/main:.claude/scripts/validate_vault.py" > "$tmp/.validator.py"
  git show "origin/main:3 - Resources/evals/lint.toml" > "$tmp/.rules.toml" 2>/dev/null || : > "$tmp/.rules.toml"
  if ! (cd "$tmp" && python3 .validator.py --rules .rules.toml --changed .changed); then
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
}

eval_skills() {
  local yardstick src f status=0
  yardstick=$(mktemp -d)
  src=origin/main
  git cat-file -e "origin/main:.claude/scripts/eval_skills.py" 2>/dev/null || src="$branch"
  for f in eval_skills validate_vault new_id; do
    git show "$src:.claude/scripts/$f.py" > "$yardstick/$f.py"
  done
  python3 "$yardstick/eval_skills.py" --ref "$branch" --yardstick origin/main "$@" || status=$?
  rm -rf "$yardstick"
  return "$status"
}

if [[ "$action" == open ]]; then
  git push -q origin "$branch"
  check
  git request-pull origin/main "$origin_url" "$branch"
  exit 0
fi

check
git switch -q main
git merge -q --ff-only origin/main
summary=$(git request-pull origin/main "$origin_url" "$branch")
git merge -q --no-ff --no-commit "$branch" || { git merge --abort; exit 1; }
scope=(--changed origin/main)
[[ "${EVALS:-0}" == "1" ]] && scope=()
eval_skills ${scope[@]+"${scope[@]}"} || { git merge --abort; exit 1; }
if [[ "${EVALS:-0}" == "1" ]]; then
  python3 .claude/scripts/measure_agent.py || { git merge --abort; exit 1; }
fi
git add -- "3 - Resources/evals/results"
git add -- "4 - Archives/raw/sessions"
git commit -q -m "PR $branch" -m "$summary"
git push -q origin main
git log -1 --format='accepted: %h %s'
