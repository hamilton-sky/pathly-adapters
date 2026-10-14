# Port the floor guard over git working-tree snapshots

Type: task
Status: resolved
Blocked by: —
Test first: yes
Floor: allow skip, suppress, empty-catch, threshold, trivial-assert

Add `src/pathly_orchestrator/proof/tree.py` and `proof/floor.py`. Both are stdlib only (create
`proof/__init__.py` if it does not exist yet) and import nothing else from `pathly_orchestrator`.

`proof/tree.py` snapshots a working tree without touching the repo's index or `HEAD`:

- `snapshot(root)`: copy the file `git rev-parse --git-path index` names to a temp file (start
  empty when there is none), set `GIT_INDEX_FILE` to the copy, run `git add -A`, then
  `git write-tree`. Return the tree id. The temp file is always removed.
- `head(root)`, `changes(root, a, b, paths=None)` (`git diff --name-status --no-renames`),
  `diff_text(root, a, b, paths=None, exclude=None)` (`git diff --no-color --unified=0
  --no-renames`, then `--`, then `paths` and each `exclude` entry as a `:(exclude)<path>`
  pathspec; with only exclusions, git diffs every other path) and `blob(root, tree, path)`
  (`git rev-parse <tree>:<path>`, `None` when absent).

Every function returns `None` (or an empty result) when `root` is not the top folder of a git
work tree, or git fails, so callers can fail open. "Top folder" means `git rev-parse
--show-toplevel` names `root` (compare `os.path.realpath` and `os.path.normcase` of both): in a
project that sits inside a larger repo, git would name paths from the outer folder, and every
`pathly/...` prefix the callers use would miss. Each git call has a 60-second timeout and runs with
`cwd=root`. See map.md § Decisions so far for the git behaviour this relies on.

`proof/floor.py` ports `/home/claude/hamilton-sky/feature-flow/feature_flow/floorguard.py`:
copy the regexes and content rules, not the CLI.

`scan(root, base, after, *, allow, protected, may_change, config_commands) -> FloorReport`
diffs the two trees.

- Outside `pathly/`, the added lines give `skip`, `suppress`, `empty-catch`, `threshold` and
  `trivial-assert`, with `FOCUSED` counted as `skip` in test files.
- Deleted test files (status `D` matching `DELETED_TEST`) give `test-delete`.
- `config` comes from `CONFIG` file names plus the content rules for `pyproject.toml`,
  `setup.cfg`, `package.json` and `conftest.py`. A `Makefile` counts only when one of
  `config_commands` starts with `make`.
- Any changed path under a `protected` prefix gives `plan-edit`, unless `may_change(path)` says
  yes.
- `count_assertions` (more assertion lines removed than added in test files) gives a warning,
  not a finding.
- Categories in `allow` are dropped from the findings.

`CATEGORIES` and `parse_allow` are as in spec.md § Interfaces. The `task-edit` category is
listed here but checked by its callers, which hold the DB rows.

Living docs: a "Floor guard" paragraph in `src/pathly_orchestrator/CLAUDE.md` (the categories,
that patterns apply outside `pathly/`, and the snapshot mechanism), credited to feature-flow
(MIT).

The `Floor:` line above is needed because this ticket's own source is the pattern list, and its
tests feed it the lines it must catch.

## Not in this ticket

- Calling the scan from a gate or from the goal-loop drain: tickets 05 and 06.
- Deciding which storage files a role may write (the `may_change` callback's logic): ticket 04.

## Done when

- `python -m pytest tests/fsm_flows/test_proof_tree.py -q -p no:cacheprovider` passes, using a
  `git init` repo under `tmp_path`. It covers: a snapshot sees a modified tracked file, a new
  untracked file and a deletion, and ignores a `.gitignore`d file; the index file's bytes, read
  just before and just after `snapshot`, are equal, and `HEAD` is unchanged; `blob` finds a path's blob;
  `diff_text(..., exclude=["pathly/"])` shows a change in `src/` and none under `pathly/`;
  outside a git repo, and in a subfolder of one, every function returns `None` or empty.
- `python -m pytest tests/fsm_flows/test_proof_floor.py -q -p no:cacheprovider` passes. It
  covers one finding per category (a `@pytest.mark.skip`, a `# noqa`, a one-line
  `except ...: pass`, a deleted `tests/test_x.py`, a `fail_under` change, an `assert True` in a
  test file, a `pytest.ini` edit, a `[tool.pytest.ini_options]` edit in `pyproject.toml`, and a
  protected plan file edit). It also covers: an allowed category gives no finding; a skip
  written in a file under `pathly/` gives no `skip`; `may_change` returning true clears a
  `plan-edit`; removed assertions give a warning only; `parse_allow(["nope"])` raises
  `ValueError`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_proof_tree.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_proof_floor.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Interfaces (`proof/tree.py`, `proof/floor.py`), § Edge cases (git missing, unmerged
  index, prose under `pathly/`)
- `/home/claude/hamilton-sky/feature-flow/feature_flow/floorguard.py` (read-only; MIT)
- map.md § Decisions so far (git docs, including pathspecs for `exclude`)

## Answer

Work started at commit `97a7b6eb780575dabf88963389aa9b93caf90d6f`. Test-only commit: `780155c`
(`test(build-proof): 02 failing test`). At that commit both Done-when commands fail at
collection with `ImportError: cannot import name 'tree'` / `'floor' from
'pathly_orchestrator.proof'` (exit 2). Round 1 code: `6a81d1b`. The review fixes start at
`8ae4c29` (the findings commit) and are one new commit on top.

**Built**

- `src/pathly_orchestrator/proof/tree.py` (new, 226 lines, stdlib only): `snapshot`, `head`,
  `changes`, `diff_text(root, a, b, paths=None, exclude=None, unified=0)`, `blob`, `read` (a
  file's text at a tree id, used by the config content rules), plus `changes_or_none` and
  `diff_text_or_none` (the same, but `None` when git fails) and `unquote_path` (a name git
  C-quotes in a patch header, unquoted). Every git call goes through one `_git` helper
  (`cwd=root`, 60 s timeout, stdout decoded UTF-8 with `surrogateescape`, inherited repo, index
  and pathspec variables dropped) and first checks `_is_top(root)` (`--show-toplevel`, compared
  after `realpath` + `normcase`). `snapshot` copies the index with `shutil.copy2`, so the copy
  keeps the real index's mtime.
- `src/pathly_orchestrator/proof/floor.py` (new, 379 lines, imports only stdlib and `.tree`):
  `CATEGORIES`, `parse_allow`, `FloorReport(findings, warnings, error=None)`, `scan(...)`,
  `count_assertions`, and feature-flow's regexes and content rules copied verbatim (`SKIP`,
  `FOCUSED`, `SUPPRESS`, `EMPTY_CATCH`, `TRIVIAL`, `THRESHOLD`, `DELETED_TEST`, `CONFIG`,
  `PYPROJECT_SECTIONS`, `SETUP_SECTIONS`, `SECTION_HEADER`, `HUNK`, `PACKAGE_KEYS`,
  `CONFTEST_WORDS`, `ASSERT_LINE`, `_section_of`, `_guarded_toml`, `_package_json_changed`).
- `src/pathly_orchestrator/proof/__init__.py`: the package docstring now names the snapshot and
  floor modules too.
- `src/pathly_orchestrator/CLAUDE.md`, § Transition gates: a "Floor guard" paragraph (the
  categories, patterns outside `pathly/` only, `FloorReport.error`, the snapshot mechanism and
  why the copy keeps the index's mtime, the `_or_none` variants and `unquote_path`, fail-open and
  the dropped environment variables, credited to feature-flow (MIT)), ending "Nothing calls the
  scan yet."
- `tests/fsm_flows/test_proof_tree.py` (new, 17 tests, 26 cases with the parametrized ones),
  `tests/fsm_flows/test_proof_floor.py` (new, 30 tests), regenerated `tests/INDEX.md` and
  `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh after the last code edit)

- `python -m pytest tests/fsm_flows/test_proof_tree.py -q -p no:cacheprovider`: `26 passed in
  3.74s`, exit 0. Covers: a snapshot sees a modified tracked file, a new untracked file and a
  deletion (`changes` == `[("A","new.py"), ("D","tests/test_app.py"), ("M","src/app.py")]`)
  and ignores a `.gitignore`d file (`blob(...,"ignored.txt") is None`); on a half-staged repo
  the `.git/index` bytes read just before and just after `snapshot` are equal and `head` is
  unchanged and equals `git rev-parse HEAD`; `blob` equals `git hash-object` and is `None` for
  a missing path; `diff_text(..., exclude=["pathly/"])` has `+++ b/src/app.py` and no
  `pathly/`, while `paths=["pathly/"]` has only the plan file; outside a repo, in `repo/src`
  (with real tree ids that do differ at the top), and with no `git` on `PATH`, `snapshot`,
  `head`, `blob` give `None` and `changes`/`diff_text` give `[]`/`""`. Also: the temp index is
  removed, a repo with no index file yet snapshots (and still has none), an index with an
  unmerged entry (`UU src/app.py`) snapshots with its bytes unchanged, no context lines at
  `unified=0`, a `None` tree id gives an empty result. Added for the review: a same-size edit
  in the second the index was written is in the snapshot (`read` gives `bbbb`); with each of
  `GIT_LITERAL_PATHSPECS`, `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS`, `GIT_ICASE_PATHSPECS`
  set to `1`, the excluded diff still shows `src/` and no `pathly/`; `unquote_path` reads `\"`,
  `\\`, `\t`, `\177` and UTF-8 octal bytes; the `_or_none` variants give `[]`/`""` for no change
  and `None` for an unknown tree id (`changes_or_none` also for a subfolder), where
  `changes`/`diff_text` give `[]`/`""`.
- `python -m pytest tests/fsm_flows/test_proof_floor.py -q -p no:cacheprovider`: `30 passed in
  6.40s`, exit 0. One finding per category: `skip: tests/test_x.py: @pytest.mark.skip`;
  `suppress: src/app.py: return a + b  # noqa`; `empty-catch: src/app.py: except ImportError:
  pass`; `test-delete: tests/test_x.py: ...`; `threshold: pyproject.toml: fail_under = 60` (with
  `config`, as `[tool.coverage.report]` is guarded); `trivial-assert: tests/test_x.py: assert
  True`; `config: pytest.ini: ...`; `config: pyproject.toml: ...` for a
  `[tool.pytest.ini_options]` edit; `plan-edit: pathly/features/demo/USER_STORIES.md: ...`.
  Also: `allow=parse_allow(["skip"])` gives no finding; `@pytest.mark.skip  # noqa` written
  into `pathly/features/demo/notes.md` gives no finding; `may_change` returning true clears the
  `plan-edit`; a removed assertion gives `findings == []` and one warning `1 assertion line(s)
  removed, 0 added...`; `parse_allow(["nope"])` raises `ValueError` naming `nope` and the valid
  categories. Extra: focused tests only in test files, `assert True` outside a test file is
  nothing, a `[project]` edit is not `config`, the Makefile, `conftest.py` and `package.json`
  content rules, scan outside a repo is empty. Added for the review: an added `++ y  # noqa`
  line gives `suppress: src/app.py: ++ y  # noqa`; files in `tests/my dir/` give
  `config: tests/my dir/conftest.py: ...` and `skip: tests/my dir/test_a.py: ...` (no TAB);
  files in a folder git quotes (`tests/odd\x7fdir/`) give the same two findings under the
  unquoted path; `GIT_LITERAL_PATHSPECS=1` still gives the `# noqa` finding; a full scan has
  `error is None`, and with every `git diff` failing the report has no findings and an error
  naming the diff; with `git cat-file` failing, the `test-delete` finding stays and the error
  names `pyproject.toml`; a missing snapshot or a non-repo root sets `error`.
- Before the fix, the same two files gave `15 failed, 41 passed`, each for the reason the
  finding names (`'aaaa\n' == 'bbbb\n'`, `'+++ b/src/app.py' in ''`, the quoted
  `skip: "b/te...` path, `[] == ['suppress: ...']`, and no `error`/`unquote_path`/`_or_none`
  yet). The `++` and TAB tests passed already: they guard behaviour that worked but was untested.
- The reviewer's probes (`scratchpad/probe02/probe.py`, `probe2.py`), run again: the quoted
  conftest now gives `config: tests/we"ird/conftest.py: ...`, `2 literal:` gives the `# noqa`
  finding, and the same-second snapshot reads `bbbb`.
- The ```check block: the same two commands, both exit 0 and print `passed` (above).
- Lint (the full chain from `commands.md`): exit 0. black `495 files would be left unchanged`;
  mypy `Success: no issues found in 281 source files`; file size `941 source files checked; 19
  known over 400 lines, none new, none grown`; mirror reads OK; `All test INDEX.md files up to
  date.`; lint-imports `Contracts: 1 kept, 0 broken.`; bandit no findings; adapters OK; entry
  points OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2445 passed, 14 skipped in 413.01s`, exit 0.

**Decisions**

- `tree.py` has its own `_git` runner rather than `proof.command.run_command`: `run_command`
  merges stdout and stderr and decodes strictly with the locale. git warnings on stderr would
  land in the parsed tree ids and diffs, and one non-UTF-8 file in a diff would make the whole
  decode fail. `_git` keeps stdout alone and decodes with `surrogateescape`, as feature-flow does.
- `_git` drops `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR` and the four
  pathspec variables (`GIT_LITERAL_PATHSPECS`, `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS`,
  `GIT_ICASE_PATHSPECS`) from the inherited environment, so `cwd=root` always names the repo and
  `:(exclude)pathly/` is always a pathspec. It passes `-c core.quotepath=off` so non-ASCII paths
  come back as text.
- The index copy uses `shutil.copy2`, which keeps the real index's mtime. git trusts an entry's
  stat data only when the entry is older than the index file and re-reads it otherwise ("racily
  clean"); a fresh mtime on the copy made a same-size edit from the second of the last index
  write look unchanged. With the mtime kept, `git add -A` on the copy sees what it would see on
  the real index.
- When the repo has no index file, the private index is left absent, not created empty: git
  refuses a 0-byte index ("index file smaller than expected"). The temp file lives in a
  `tempfile.TemporaryDirectory`, so it (and any `index.lock`) is removed on every path.
- `diff_text` also passes `--no-ext-diff --no-textconv --src-prefix=a/ --dst-prefix=b/`, so a
  user's `diff.external`, textconv filters or `diff.noprefix` cannot change the text callers
  parse. `changes` uses `-z` so paths come back exactly.
- `read(root, tree, path)` is one function beyond the ticket's list: the `pyproject.toml`,
  `setup.cfg` and `package.json` rules need both versions of the file, as feature-flow reads
  them with `git show`. Keeping it in `tree.py` keeps every git call in one module.
- The diff is parsed into files once (`_file_diffs`): `---`/`+++` are read as names only
  before a file's first `@@`, so an added line `++ x` (printed `+++ x`) is still scanned. A
  header name loses the TAB git adds after a name with a space (after the closing quote when
  the name is quoted, checked on git 2.43), then is unquoted with git's C rules (`\a \b \t \n \v \f \r \" \\` and three-digit
  octal bytes) and decoded with `surrogateescape`, as `_git` decodes the `-z` paths of
  `changes`, so the per-file diffs key on the same path `changes` gives.
- `scan` reports a failed git call in `FloorReport.error` rather than returning `None`. A
  failed `diff` still leaves the `changes`-based findings (`test-delete`, `config` by name,
  `plan-edit`) and a failed `changes` still leaves the line patterns; those are real, and a
  `None` would throw them away. `error` defaults to `None`, so the spec's
  `FloorReport(findings, warnings)` still builds. Missing snapshot ids return at once with
  `error="no snapshot to diff"`.
- Failure is detected through `tree.changes_or_none` / `tree.diff_text_or_none`, so the public
  `changes`/`diff_text` keep the ticket's "empty on failure" contract. A config file read counts
  as failed only on a side where `changes` says the file exists (`A` has no old side, `D` no new
  side), because `read` gives `None` for an absent path too.
- `scan` makes one `changes` call (all paths) and filters `pathly/` out in Python for
  `test-delete` and `config`; `plan-edit` uses the same rows. A `protected` entry matches the
  path itself or anything under it (`p` or `p/...`), so `pathly/features/x` does not cover
  `pathly/features/xyz/`. An empty prefix protects nothing.
- `scan`'s keyword arguments have defaults (nothing allowed, nothing protected, no excuser, no
  commands), so a caller passes only what it uses.
- `parse_allow` takes a list or a comma/space string, lower-cases names, skips blanks, and its
  `ValueError` names the bad entry and every valid category (ticket 03's 400 needs that).
- Finding texts for non-line findings: `test-delete: <path>: a test file was deleted`,
  `config: <path>: lint, test or CI config was changed`, `plan-edit: <path>: a protected plan
  file was added|deleted|changed`. The warning keeps feature-flow's wording.
- A `Makefile` counts when a `config_commands` entry starts with `make`, as a plain string or a
  JSON argv array (`["make", ...]`), since verify settings may be either.
- Tests: the same-second test pins the file and index mtimes with `os.utime` and sets
  `core.trustctime=false`, so it does not race the clock (the reviewer's probe aligned to a
  second boundary and slept). The quoted-name scan test uses DEL (0x7f) in a folder name, which
  git quotes and Windows allows, rather than `"`, which Windows does not; `"`, `\` and the other
  escapes are covered by the parametrized `unquote_path` test. The git-failure tests patch
  `tree._git` to fail one git subcommand, which is what a timeout looks like to the caller.

**Shortcuts taken**

- A file marked binary for diff (a `-diff` line in `.gitattributes`) shows no added lines, so
  its patterns are not scanned; `.gitattributes` is not a `config` file either. Passing `--text`
  would close that, but would put binary bytes into `diff_text`, which ticket 10 puts into
  prompts (argv cannot hold a NUL). Worth closing with a floor-only `--text` if an agent is ever
  seen doing it.
- The snapshot trusts the copied index's flags. An entry marked `--assume-unchanged` or
  `--skip-worktree` in the real index stays unstaged in the copy, so an edit to that file is not
  in the snapshot (a builder would have to run `git update-index` on purpose). Worth clearing the
  assume-unchanged bit on the private copy (`git ls-files -v`, then `git update-index
  --no-assume-unchanged`) if it is ever seen; skip-worktree is how sparse checkouts work, so it
  would need care.
- Only the repo, index and pathspec variables are dropped. Config passed down by a parent git
  process (`GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`) and `GIT_OBJECT_DIRECTORY` /
  `GIT_ALTERNATE_OBJECT_DIRECTORIES` are kept; the diff settings that change the parsed text are
  pinned on the command line anyway. `git rev-parse --local-env-vars` lists the rest if one of
  them ever matters.
- Each `tree` call runs its own `--show-toplevel` check (one extra git process per call).
  Cheap next to a snapshot; worth caching if a caller ever loops over many `blob` calls.

**Review fixes** (round 1, quality review)

1. major, racy index copy: `snapshot` now copies with `shutil.copy2`, so the private index keeps
   the real index's mtime and git's racy-clean check re-reads a same-second, same-size edit.
   Reproduced first with the reviewer's probe (`copyfile: aaaa | copy2: bbbb`), then with a new
   clock-free test (`test_snapshot_sees_a_same_size_edit_made_in_the_second_the_index_was_written`),
   which failed with `'aaaa\n' == 'bbbb\n'` before the change and passes after.
2. minor, pathspec variables: `_git` now also drops `GIT_LITERAL_PATHSPECS`,
   `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS` and `GIT_ICASE_PATHSPECS`. Tests: a tree test
   parametrized over all four (the literal one failed with `'+++ b/src/app.py' in ''` before) and
   the reviewer's floor case (`[]` before, the `# noqa` finding after).
3. minor, C-quoted names: new `tree.unquote_path`, used by `floor._diff_path` after the TAB is
   dropped, so per-file diffs key on the same path as `changes`. Tests: a parametrized
   `unquote_path` test and a scan over a folder git quotes, whose `skip` finding read
   `skip: "b/te...` before. The round 1 shortcut about quoted paths is gone with it. The
   reviewer's `tests/we"ird/conftest.py` probe now gives the `config` finding.
4. minor, untested parser branches: `test_an_added_line_that_starts_with_two_pluses_is_still_scanned`
   and `test_a_name_with_a_space_is_read_without_the_tab_git_ends_it_with` (exact finding texts,
   so a TAB left on the name or a `+++ y` line read as a header fails them). Both pass on the
   round 1 code, as the reviewer found by hand; they are regression guards.
5. minor, failure looks clean: `FloorReport` has `error: str | None = None`. `scan` sets it for a
   missing snapshot, a failed `diff` (`tree.diff_text_or_none`), a failed `changes`
   (`tree.changes_or_none`) and a failed read of a config file that exists on that side, and
   keeps the findings it did make. Tests: a git `diff` failure (findings `[]`, error names the
   diff, where the same scan with git working gives `suppress` and `test-delete` and no error), a
   `cat-file` failure (the `test-delete` finding stays, error names `pyproject.toml`), and a
   missing snapshot or non-repo root. The round 1 shortcut "scan fails open silently" is gone.

**For later tickets**

- Import as `from pathly_orchestrator.proof import floor, tree`. `tree.snapshot(root)` returns
  `None` outside a repo top, so store `None` and skip; `tree.changes/diff_text/blob/read` accept
  a `None` tree id and return empty/`None`. Use `tree.changes_or_none` /
  `tree.diff_text_or_none` where a git failure must not read as "no change" (tickets 04, 09).
- `floor.scan(root, base, after, allow=..., protected=[...], may_change=fn, config_commands=[...])`
  returns `FloorReport(findings, warnings, error)`. Tickets 05 and 06: findings fail the
  attempt or gate (they are real even when `error` is set); with no findings and an `error`,
  log the skip (`GATE_SKIPPED` with the error text) instead of treating the scan as clean.
- Ticket 06 should pass `config_commands` from the `verify.*` settings so a `Makefile` counts
  when the project builds with make. Ticket 04's `may_change(path)` gets repo-relative POSIX
  paths (as git prints them, unquoted).
- Ticket 03 can validate an allow list with `floor.parse_allow(list)` and use the
  `ValueError` text in the 400 body.
- `tree.blob(root, tree, path)` returns `None` both for an absent path and outside a repo;
  ticket 04's "current blob equals a window's after-blob" comparison should treat `None ==
  None` (both deleted) as explained only when both trees exist.
- The `task-edit` category is accepted by `parse_allow` and dropped by `allow`, but `scan`
  never produces it: tickets 05/06 add it themselves, after checking `allow`.

## Review findings (round 1, quality review)

Scope: I reviewed 97a7b6eb..6a81d1b. 6a81d1b is the newest commit that touches the ticket, and it is also HEAD, so no later commits were left out. I read the ticket as it was at the base commit. I never read the `## Answer`, from the ticket or from its hunk, and only grepped the hunk's Status line (open -> resolved). Working tree is clean.

What I ran:
- Both Done when commands pass (13 passed, 23 passed).
- I also ran black, mypy and bandit on `proof/`, plus `check_file_size.py` and `gen_test_index.py --check`. All clean.
- I tested edge cases with throwaway scripts outside the repo. They are still at `/tmp/claude-0/-home-claude-pathly-adapters/336d5e39-1571-55c5-869b-9ea565351722/scratchpad/probe02/probe.py` and `probe2.py`; the temp git repos they made were cleaned up.

QUALITY
1. major /home/claude/pathly-adapters/src/pathly_orchestrator/proof/tree.py: `snapshot` can miss a real working-tree change. It copies the index with `shutil.copyfile`, which gives the copy a new mtime. Git uses the index file's mtime to spot "racily clean" entries: a file edited in the same second the index was last written, with its size unchanged. With a newer mtime on the copy, `git add -A` treats that file as unchanged and the tree records the old blob. Reproduced on git 2.43, both in a fresh repo and in one with commits: write `f.py` as `aaaa`, `git add -A`, rewrite it as `bbbb` in the same second, then snapshot 2 s later. The snapshot holds `aaaa` while `git status` shows the file modified. Doing the same with `shutil.copy2` gives `bbbb`. A same-size edit like `assert a == b` -> `assert a == a` (a trivial-assert) would be invisible to the after-snapshot. Index writes are frequent here: `git status` runs in the agent, in an IDE, and in Pathly's own provenance capture and scope gate. Tickets 04, 05, 06 and 09 all build on this snapshot - use `shutil.copy2` so the copy keeps the real index's mtime, and add a test that does the same-second, same-size edit and checks the snapshot holds the new blob.
2. minor /home/claude/pathly-adapters/src/pathly_orchestrator/proof/tree.py: `_git` strips `GIT_DIR`/`GIT_INDEX_FILE`/etc. but not the pathspec variables. With `GIT_LITERAL_PATHSPECS=1` inherited, `:(exclude)pathly/` is read as a literal path name, so `diff_text` comes back empty and `floor.scan` silently reports no pattern or content-rule findings. Reproduced: one `# noqa` edit is found normally and gives `[]` with the variable set - add `GIT_LITERAL_PATHSPECS`, `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS` and `GIT_ICASE_PATHSPECS` to the stripped variables.
3. minor /home/claude/pathly-adapters/src/pathly_orchestrator/proof/floor.py: `_diff_path` does not undo git's C-style quoting of `---`/`+++` names, which `core.quotepath=off` does not turn off for `"`, `\` or control characters. The quoted name then never matches the unquoted `-z` path from `changes`, so the content rules lose their hunks and added lines. Reproduced: adding `collect_ignore` to `tests/we"ird/conftest.py` gives no `config` finding - unquote quoted header names, or key the per-file diffs on something that matches `changes()`.
4. minor /home/claude/pathly-adapters/tests/fsm_flows/test_proof_floor.py: two parser branches have no test. One is the "names only before the first `@@`" rule: an added line `++ x` prints as `+++ x`. The other is stripping the TAB git puts after a name containing a space. Both work (I checked by hand), but nothing would catch a regression - add one test per case.
5. minor /home/claude/pathly-adapters/src/pathly_orchestrator/proof/floor.py: `scan` cannot tell "git failed" from "nothing found". `diff_text` turns a git failure (for example the 60 s timeout on a huge diff) into `""` and `changes` into `[]`, so the report is just clean. The spec's edge-case table asks for a `GATE_SKIPPED`/log line when git fails, and ticket 06's `floor_gate` will have nothing to base it on once both snapshots have succeeded - let `FloorReport` carry a skipped/error flag, or let `scan` return `None` when a git call fails.

REVIEW: FAIL
