---
name: query
description: Answers questions about the vault's content by citing the note IDs. Use when asked what the vault knows, where something was decided, who does what or what is still open.
model: sonnet
effort: high
disallowed-tools: WebSearch, WebFetch
---
Question: $ARGUMENTS

1. Read `index.md`.
2. Filter with `rg` before opening notes: by id (`rg -l '\bF0042\b'`), by source (`rg -l '^sources:.*\bS0042\b'`), by status (`rg -l '^status: open'`), by owner (`rg -l '^owner: Ana'`).
3. Open only the notes you need and cite the id of each claim in the answer.
4. Dates, counts and "how many" or "when": use `python3 .claude/scripts/facts.py count` or `rg -c`, do not estimate.
5. If the vault does not have the answer, say you don't know. Do not fill in with outside knowledge.
6. `4 - Archives/raw/sessions/` only comes in if the question is about a session; start from the LS note.
7. An answer worth keeping: `python3 .claude/scripts/new_note.py question "<question>"` and close it with the answer and the citations.
