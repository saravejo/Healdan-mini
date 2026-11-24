# Changelog

## 1.1 (2026-11-24)

Two targeted changes, so that the vault behaves the same way in production, session after session.

### Every skill has an eval

- **`eval_skills.py`**, the harness. Each case runs N times, each time in a fresh session and in a disposable vault built from the commit under evaluation, with its own origin, no memory and no MCP. The verdict has three yardsticks:
  - **safety:** 100% of the repetitions;
  - **quality:** at least 2 out of 3 by default;
  - **predictability:** the same signature (notes created, IDs cited, validator) in at least 2 out of 3.

  The summary of each run and the transcript of each execution go to `3 - Resources/evals/results/skills/`.
- **`skill-evals.md`**, one eval for each of the five skills, with at least one safety case and one quality case:

  | Skill | Cases |
  |---|---|
  | `ingest` | minutes with a decision and an activity · injection in the source · source already registered |
  | `query` | cites the decision · counts without estimating · doesn't know and says so · injection in a note |
  | `review` | full review · failing test question |
  | `improve` | one experiment · frozen yardstick |
  | `close-session` | closes with a PR · request to accept its own PR |
- **Validator:** refuses a skill without an eval or with an incomplete eval:
  - a safety or quality case is missing;
  - fewer than 2 repetitions;
  - a prompt that does not call the skill;
  - an unknown check or an invalid regex.

  The hook flags this right when `SKILL.md` is edited.
- **Gates:**
  - `pr.sh accept` runs the evals of the affected skills, with `main`'s harness and evals, and undoes the merge if any fails;
  - `EVALS=1` runs all of them;
  - `experiment.py measure` drops (`crash`) the experiment whose touched skill fails, before spending the round of test questions;
  - `pr.sh check` warns when the branch changes the yardstick.
- **Skills:**
  - **Least privilege:** `disallowed-tools: WebSearch, WebFetch` in all five. The plan was to use `allowed-tools`, but it pre-approves tools instead of restricting them.
  - **Two adjustments showed up while writing the evals:**
    - `ingest` did not say where to save the extractor's JSON; now it goes to `4 - Archives/sessions/<LS>.items-<S>.json`;
    - `review` recorded a self-assessment without opening an LS note; now it opens one.

### Auto memory off

- `"autoMemoryEnabled": false` in `settings.json`. The validator refuses the vault when:
  - the key is missing, or it is `true`;
  - `settings.local.json` turns memory on;
  - some subagent declares `memory:`.

  Since the origin judges with `main`'s validator, a PR cannot turn memory back on.
- `measure_agent.py` and `eval_skills.py` run `claude -p` with `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- What is worth remembering becomes an L or IN note, or a line in `CLAUDE.md`, always through a PR. `CLAUDE.md` and the `close-session` skill say so.

### Installation and integrity

- `SHA256SUMS` in the kit. `install.sh` checks the kit before installing, unless `KIT_EDITED=1` is passed.
- In a vault that already exists, `install.sh` adds the missing evals and the `autoMemoryEnabled` key. It does not overwrite skills or templates, so, to update from 1.0, also run `new_note.py --extract-templates templates.md --force` on a branch (section 17).

### Main text

- Section 9 became "Measurement: test questions and skill evals".
- Principles 15 (every skill has an eval) and 16 (no implicit memory).
- Memory off and least privilege in section 5.
- Adjustments in sections 2, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17 and 18.

### Tests

The regression went from 103 to 169 checks, including updating a 1.0 vault from the frozen zip. The eval and gate checks use a simulated `claude` in three versions (correct, unsafe and unstable) to show three things:

- the harness judges correctly;
- the kit's evals can be satisfied by correct behavior;
- the gates block what fails.

None of this replaces the baseline in your environment: the evals have not yet run against the real model.

## 1.0 (2026-11-24)

First frozen version. It has 23 files, byte-for-byte identical to the `vault-kit.zip` delivered before (sha256 `a181262e42411a9dd1e52202a5718bc1198fea5f3f338ef04b42eca83255c1cf`), plus `SHA256SUMS`.

- **Tag:** `v1.0`, tree `0212dada242270e0652e35e540a17659329d7d0f`.
- **Zip:** `git archive --format=zip --prefix=vault-kit-1.0/ v1.0`, sha256 `23ae410067710ae1f6c2cd647771f15a12e148b8a49569c33e79ef7955f50a7b`.
- **Regression:** 104 checks. These are the 103 from the suite plus the `SHA256SUMS` one.
