---
name: improve
description: Improves the vault with measured experiments in the autoresearch style, one change at a time, keeping only what improves the score or simplifies. Use when a metric got worse, a lesson repeated or the human asks to improve the vault.
disable-model-invocation: true
argument-hint: "<tag> <how many experiments>"
disallowed-tools: WebSearch, WebFetch
---
Request: $ARGUMENTS

1. Open an IN note with the overall hypothesis and `python3 .claude/scripts/experiment.py start <tag>`.
2. Repeat up to the requested number of experiments:
   - Pick one concrete hypothesis from the L lessons, the failing test questions and the hallucination report. Read `experiment.py report` first so you do not repeat what was already discarded.
   - Change only the surface: `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/agents/`, `3 - Resources/templates/`. Never test questions, skill evals, lint rules or measurement scripts.
   - One commit, then `python3 .claude/scripts/experiment.py measure "<what you tried>"`. The script decides and reverts on its own. If the change touches a skill, its eval runs before the test questions and, if it fails, the experiment crashes.
   - Prefer removing to adding: deleting text with the same score is a win.
3. At the end, `experiment.py report`, fill in the IN with the result and open the PR with `pr.sh open experiment/<tag>`.
