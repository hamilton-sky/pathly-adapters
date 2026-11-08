# A working-tree snapshot survives a temp file that vanishes mid-add

Type: task
Status: open
Blocked by: 19
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/proof/tree.py, tests/fsm_flows/test_proof_tree_vanishing_file.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/fsm_flows/INDEX.md

The person chose (2026-11-08, on PR #138) to merge, then fix this race. CI's full suite fails at
random in `tests/fsm_flows/test_build_proof_acceptance.py` (test_1, test_7 or test_8: a floor
check is missing, `FLOOR_CHECKED 3 != 4`), and the file passes when run alone.

Cause: the DB->disk mirrors (`event_mirror.py`, `board_mirror.py`, `eventlog.py`) write
`<name>.tmp` next to the file and `os.replace` it. `proof/tree.snapshot` runs `git add -A` on a
private index. When a `.tmp` file is listed and then renamed away before git stats it, git exits
with `fatal: unable to stat '<path>.tmp': No such file or directory`, `snapshot` returns None, and
the floor gate skips (`snapshot_failed`). Measured in the scratchpad: a loop renaming 50 `.tmp`
files made 36 of 200 `git add -A` runs fail this way.

Fix it in `proof/tree.py`, which stays stdlib-only with no Pathly imports. When `git add -A` fails
**only** because a path vanished (git's stderr says `unable to stat` ... `No such file or directory`),
run the add again on the same private index, up to 3 attempts in all. Any other failure still
returns None at once, as today. The other functions do not change. Keep `_git`'s callers' return
contract (stdout or None): read stderr through a new helper, or an option, not by changing what
`_git` returns.

Document the retry in `src/pathly_orchestrator/CLAUDE.md`, in the floor guard paragraph where
`tree.snapshot` is described.

## Not in this ticket

- Moving the mirrors' temp files out of the tree, or making the floor gate fail closed on
  `snapshot_failed`. Each changes more than the race needs.

## Done when

- `python -m pytest tests/fsm_flows/test_proof_tree_vanishing_file.py -q -p no:cacheprovider`
  passes and covers, deterministically (patch the subprocess run, no timing): a first `git add -A`
  that fails with the vanished-path message and a second that succeeds gives a tree id; three
  vanished-path failures in a row give None and no fourth attempt; a failure with any other
  message gives None after one attempt; and a real repo snapshot still equals `git write-tree` of
  the same files.
- `python -m pytest tests/fsm_flows -q -p no:cacheprovider` passes, and
  `python scripts/gen_test_index.py --check` passes.
