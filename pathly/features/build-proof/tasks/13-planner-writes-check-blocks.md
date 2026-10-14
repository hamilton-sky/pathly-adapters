# Teach the planner to write check blocks into board tasks

Type: task
Status: open
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
