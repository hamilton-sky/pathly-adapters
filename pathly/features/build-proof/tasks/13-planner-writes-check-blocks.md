# Teach the planner to write check blocks into board tasks

Type: task
Status: resolved
Blocked by: 01
Test first: no

The supervisor now runs a task's ```check block, so the planner should write one wherever a
command can prove the task.

- `src/pathly_data/core/skills/planning/plan.md`: in "Task Decomposition Rules", replace the
  `Verify:` field with a `Check:` field. It holds a ```check block in the supervisor's grammar
  (`$ <command>`, `exit <N>|nonzero`, `prints <text>`). Commands are read-only, run from the repo
  root, use no shell features (one `$` line per command, no `&&` or pipes), and use the
  project's real commands. It is required at standard and strict rigor, and optional in lite.
  When nothing can be checked by a command, the field says so in one line, and the reviewer
  reads the code instead. Update the "Standard/strict … File + Done when + Verify" line and
  Step 5's "Verify commands use correct project commands" line to match.
- `src/pathly_data/core/skills/fragments/task-dag-post.md`: say that a task's `text` carries
  the phase's ```check block verbatim (JSON-escaped newlines in the curl body, with one short
  example). The supervisor runs it after the task reports success, from the text as it was
  when the task was claimed, so the block must be right before posting. Note that `files` also
  sets the task's scope for `scope_gate`.
- Regenerate every golden snapshot that changes: run
  `python -m pytest tests/install_skills/test_compose.py`, and for each drifting skill write
  `compose_skill(<skill>, "claude")` to `tests/snapshots/<skill with / as __>.claude.md`.

Add `tests/install_skills/test_planner_check_blocks.py`. It extracts the ```check example from
`compose_skill("planning/plan", "claude")` and from the `task-dag-post` fragment text, and
checks that `proof.checks.checks_in` parses each into at least one `Check`. A later wording
change cannot then break the grammar unnoticed.

Living docs: the `task-dag-post` line in `src/pathly_data/CLAUDE.md` (tasks carry check blocks).

## Not in this ticket

- Running the blocks: ticket 05 (goal-loop) and ticket 07 (team flows).
- The `development/*` interactive skills and the `IMPLEMENTATION_PLAN.md` template under
  `templates/plan/`: unchanged unless a snapshot test forces it.

## Done when

- `python -m pytest tests/install_skills/test_planner_check_blocks.py -q -p no:cacheprovider`
  passes.
- `python -m pytest tests/install_skills/test_compose.py -q -p no:cacheprovider` passes with the
  regenerated snapshots.
- `planning/plan.md` no longer asks for a `Verify:` field:
  `python -c "import pathlib;t=pathlib.Path('src/pathly_data/core/skills/planning/plan.md').read_text(encoding='utf-8');print('clean' if '- Verify:' not in t else 'still there')"`
  prints `clean`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/install_skills/test_planner_check_blocks.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/install_skills/test_compose.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib;t=pathlib.Path('src/pathly_data/core/skills/planning/plan.md').read_text(encoding='utf-8');print('clean' if '- Verify:' not in t else 'still there')"
exit 0
prints clean
```

## Reference

- spec.md § Decisions ("Where a check block lives", "How a check command runs")
- `src/pathly_data/core/skills/planning/plan.md` ("Task Decomposition Rules", "Step 5")
- `src/pathly_data/core/skills/fragments/task-dag-post.md`
- `tests/install_skills/test_compose.py` (`test_team_skill_matches_golden_snapshot`)

## Answer

Work started at commit `b02735f65205641b801d15881f22e6a9ba79a7ac`. `Test first: no`, so there is
no test-only commit.

**Built**

- `src/pathly_data/core/skills/planning/plan.md`: in "Task Decomposition Rules" the `Verify:`
  field is now `Check:` (a ```check block; required at standard and strict, optional in lite).
  A new paragraph after the `File`/`Done when` paragraph shows one pytest example block and lists
  the grammar (`$ <command>`, `exit <N>|nonzero`, `prints <text>`, `#` and blank lines), that
  commands are read-only and run from the repo root, that no shell runs them (one `$` line per
  command, no `&&`, `|`, `;`, redirects or `$VARIABLES`), that they are the project's real
  commands, and that `Check: none - <why>` on one line stands in when no command can show the
  phase is done (the reviewer then reads the code). The "Standard/strict ... File + Done when +
  Verify" line says `Check`, and Step 5's "Verify commands use correct project commands" line is
  now "Every phase has a `Check:` block (or a one-line `Check: none - <why>`) at standard and
  strict; its commands are the project's real commands, one `$` line each, with no shell
  features".
- `src/pathly_data/core/skills/fragments/task-dag-post.md`: a new "`text` carries the phase's
  check block" section (the block goes at the end of `text` verbatim; the supervisor runs it
  after the task reports success, from the text as it was when the task was claimed, so it must
  be right before posting; a `Check: none` phase posts no block), with a plain ```check example
  and the same block as a JSON-escaped `"text"` string (`\n` newlines, `\"` for a quote). The
  `lane`/`files` section ends with one sentence: `files` also sets the task's scope for
  `scope_gate`.
- `tests/snapshots/planning__plan.claude.md`: regenerated from
  `compose_skill("planning/plan", "claude")`. It was the only snapshot that drifted.
- `tests/install_skills/test_planner_check_blocks.py` (new, 4 tests) and the regenerated
  `tests/INDEX.md`, `tests/install_skills/INDEX.md`.
- `src/pathly_data/CLAUDE.md`: the `planning/plan` ... `task-dag-post` sentence in the
  Agnosticism paragraph says a task's `text` carries its phase's ```check block verbatim, and
  names the new test.
- `map.md` (one Decisions line) and `learnings.md` (one line).

**Proof** (each run fresh after the last edit, dev venv first on PATH)

- `python -m pytest tests/install_skills/test_planner_check_blocks.py -q -p no:cacheprovider`:
  `4 passed in 0.09s`, exit 0. The tests: `checks_in` on `compose_skill("planning/plan",
  "claude")` gives at least one `Check`; the same on the `task-dag-post` fragment text; the
  fragment's `"text": "..."` JSON example, `json.loads`-ed, parses to the same checks as the
  plain block; and `compose_skill("planning/plan", build_adapter_caps("claude", goal_id="g1"))`
  (which includes the fragment) parses with at least as many checks as the two parts. Every
  example command is also checked for `&&`, `||`, `|`, `;`, `>` and `<`.
- `python -m pytest tests/install_skills/test_compose.py -q -p no:cacheprovider`: `97 passed in
  2.43s`, exit 0. Before the snapshot was regenerated the same command gave `1 failed, 96
  passed`: only `test_team_skill_matches_golden_snapshot[planning/plan]`, on the `Verify:` ->
  `Check:` line.
- The `python -c` check on `planning/plan.md` printed `clean`, exit 0.
- Lint command from `commands.md`, run as one chain: exit 0 (black `523 files would be left
  unchanged`; mypy `Success: no issues found in 293 source files`; file size `none new, none
  grown`; mirror reads OK; test INDEX up to date; lint-imports `1 kept, 0 broken`; bandit no
  findings; adapters OK; entry points OK).
- Smoke: exit 0. Build (`python -m build --wheel`): exit 0.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2695 passed, 14 skipped in
  433.08s`, exit 0.

**Decisions**

- The ```check example sits in `plan.md`'s body, not in the fragment only, because the golden
  snapshot and the new test compose `planning/plan` without a `goal_id`, and the fragment is
  `requires: goal_id`-gated, so it is absent there. Both texts therefore carry their own example,
  and the fourth test pins that the two compose together without a stray open fence.
- The fragment shows the block twice: a plain ```check fence (what `checks_in` reads) and the
  JSON-escaped `"text"` string for the curl body. A fence shown mid-line inside a JSON string is
  not a block to `checks_in` (it reads only lines that start with the fence), so the JSON form
  does not double-count. The test decodes the JSON form and compares it with the plain block, so
  the two cannot drift apart.
- The `Check:` rules say "no `$VARIABLES`" as well as "no `&&` or pipes": `run_command` uses
  `shlex.split` and no shell, so `$HOME` would reach the program as a literal.
- Step 6 of `plan.md` ("Compose the self-contained task `text` ...") is not edited: the ticket
  puts the carry-through rule in the fragment, which Step 6 already defers to for the POST
  mechanics.

**Shortcuts taken**

- none

**For later tickets**

- Tickets 05 and 07 (and 14): a planner following the new text writes the block at the end of
  the task `text`, so `checks_in` finds it with no `## Done when` heading. A phase marked
  `Check: none - <why>` posts no block, which is the `TASK_PROOF checks: "none"` case, not a
  failure. A planner that writes a block with a bad line produces text `checks_in` rejects with
  `ParseError`, which the callers must treat as a failed check.
- `src/pathly_data/core/templates/plan/IMPLEMENTATION_PLAN.template.md` still shows
  `**Verify:**` (the ticket leaves the template unchanged, and no snapshot forced a change), so
  the template and the skill now name the field differently until a human decides to align them.
  `development/build.md` still says `Verify:` too.
- `src/pathly_orchestrator/CLAUDE.md` still says of the check-block grammar "Nothing runs them
  yet" (ticket 01's note): ticket 05 or 07 changes it when `run_checks` is wired in.
