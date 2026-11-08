# A working-tree snapshot survives a temp file that vanishes mid-add

Type: task
Status: resolved
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

## Answer

Base: f6a6bde8311c042bca7de2f56436a45ca03c358c. Failing test commit: 2d71f95.

- **Built**: `src/pathly_orchestrator/proof/tree.py` (new `_git_run` returns the finished
  `CompletedProcess` or None; `_git` is built on it with the same stdout-or-None contract;
  `_vanished` reads stderr for `unable to stat` + `No such file or directory`; `_add_all` runs
  `git add -A` on the private index up to `ADD_ATTEMPTS = 3` times while only a path vanished;
  `snapshot` calls it; 259 lines, stdlib only); `src/pathly_orchestrator/CLAUDE.md` (floor gate
  paragraph, after the `tree.snapshot` description); new
  `tests/fsm_flows/test_proof_tree_vanishing_file.py` (5 tests); `tests/INDEX.md`,
  `tests/fsm_flows/INDEX.md`.
- **Proof**:
  - `python -m pytest tests/fsm_flows/test_proof_tree_vanishing_file.py -q -p no:cacheprovider`:
    5 passed (at 2d71f95: 2 failed, the retry tests, `assert 1 == 2` / `1 == 3` adds). Covers:
    vanished then clean add gives the tree id equal to `git write-tree` (2 adds); three vanished
    failures give None with exactly 3 adds; another message (`index.lock`) gives None after 1 add;
    a `No such file or directory` without `unable to stat` is not retried; a real snapshot equals
    `git write-tree` of the same files. `subprocess.run` is patched for `add -A` only.
  - `python -m pytest tests/fsm_flows -q -p no:cacheprovider`: 719 passed, 9 skipped (the skips
    were there before), exit 0.
  - `python scripts/gen_test_index.py --check`: "All test INDEX.md files up to date.", exit 0.
  - Also clean: black, mypy on tree.py, `check_file_size.py` (none new, none grown),
    `lint-imports` (1 kept), bandit on tree.py.
- **Decisions**: a separate `_git_run` helper rather than an option on `_git`, so every `_git`
  caller is untouched. A failed `git add` rolls back its lock, so the retry reuses the same private
  index. A run git cannot start (None) is not retried.
- **Shortcuts taken**: 3 attempts, as the ticket says. A scratchpad stress loop (renames with no
  pause, far busier than the debounced mirrors) still beats 3 in a row now and then: with 50
  churning files, `snapshot` None went from 112/200 to about 12/200; with 3 files, from 110/200
  to 32/200. Every remaining failure was the vanished-path case. If the flake comes back in CI,
  the next steps are a short pause between attempts, more attempts, or moving the mirrors' temp
  files out of the tree (out of scope here).
- **For later tickets**: 12 — the acceptance flake (`FLOOR_CHECKED 3 != 4`) should now be rare,
  but it can still happen under heavy mirror churn (see Shortcuts).
