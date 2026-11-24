---
name: close-session
description: Closes the work session in the vault with an LS note, decision trail, self-assessment and an open PR.
disable-model-invocation: true
disallowed-tools: WebSearch, WebFetch
---
1. Fill in the session's LS note (or create it with `python3 .claude/scripts/new_note.py session "<goal>" --field session_id=${CLAUDE_SESSION_ID}`): goal, what was created and changed, verification done. Set `status: closed` and `branch:` to the current branch.
2. Write the trail in `4 - Archives/sessions/<LS>.decisions.tsv`: `ts	phase	decision	why	evidence	result`, one line per decision. The `ts` comes from `python3 .claude/scripts/facts.py now`.
3. For each mistake that repeated, create an L; if the fix fits in a script or rule, an IN. This is how the vault remembers: auto memory stays off, and whatever does not become a note does not carry over to the next session.
4. Record the self-assessment: `python3 .claude/scripts/evaluate_agent.py record --session <LS> --checked N --unsupported N --hallucinations-subagent N --hallucinations-session N`, with the numbers from `check_items.py` and from the reviewers.
5. `python3 .claude/scripts/validate_vault.py` until `vault ok`, commit and `bash .claude/scripts/pr.sh open <branch>`.
