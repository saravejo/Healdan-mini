---
name: review
description: Weekly review of the vault, the LLM Wiki lint. Runs the full validator, judgment reviews in parallel slices, the hallucination report and the test questions. Use when asked for a review, lint or cleanup of the vault.
disable-model-invocation: true
disallowed-tools: WebSearch, WebFetch
---
Copy these steps to the task list.

1. Open the session note: `python3 .claude/scripts/new_note.py session "Weekly review" --field session_id=${CLAUDE_SESSION_ID}`.
2. `python3 .claude/scripts/validate_vault.py` and `python3 .claude/scripts/facts.py count`. Note errors, orphans, a stalled inbox and overdue activities.
3. Dispatch one `qa-structure` per folder of `2 - Wiki/` and one for `1 - Projects/`, in the same message. Also ask for contradictions between current F and forgotten mature ideas.
4. `python3 .claude/scripts/evaluate_agent.py report --since <7 days ago, from facts.py>`.
5. `python3 .claude/scripts/measure_agent.py`.
6. Turn each finding into a note: Q for a gap, A for a task, L for a repeated mistake, IN for a structural change. The yardstick (`3 - Resources/evals/`) is not corrected: a failing test question becomes a Q, L or IN, never an edit to the question.
7. Line in the log: `## [<date from facts.py now>] lint | - | <one-line summary>`.
8. Fill in the LS, record the self-assessment with `evaluate_agent.py record --session <LS>`, commit and run `pr.sh open <branch>`.
