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
'pathly_orchestrator.proof'` (exit 2).

**Built**

- `src/pathly_orchestrator/proof/tree.py` (new, 170 lines, stdlib only): `snapshot`, `head`,
  `changes`, `diff_text(root, a, b, paths=None, exclude=None, unified=0)`, `blob`, and `read`
  (a file's text at a tree id, used by the config content rules). Every call goes through one
  `_git` helper (`cwd=root`, 60 s timeout, stdout decoded UTF-8 with `surrogateescape`) and
  first checks `_is_top(root)` (`--show-toplevel`, compared after `realpath` + `normcase`).
- `src/pathly_orchestrator/proof/floor.py` (new, 354 lines, imports only stdlib and `.tree`):
  `CATEGORIES`, `parse_allow`, `FloorReport(findings, warnings)`, `scan(...)`,
  `count_assertions`, and feature-flow's regexes and content rules copied verbatim (`SKIP`,
  `FOCUSED`, `SUPPRESS`, `EMPTY_CATCH`, `TRIVIAL`, `THRESHOLD`, `DELETED_TEST`, `CONFIG`,
  `PYPROJECT_SECTIONS`, `SETUP_SECTIONS`, `SECTION_HEADER`, `HUNK`, `PACKAGE_KEYS`,
  `CONFTEST_WORDS`, `ASSERT_LINE`, `_section_of`, `_guarded_toml`, `_package_json_changed`).
- `src/pathly_orchestrator/proof/__init__.py`: the package docstring now names the snapshot and
  floor modules too.
- `src/pathly_orchestrator/CLAUDE.md`, § Transition gates: a "Floor guard" paragraph (the
  categories, patterns outside `pathly/` only, the snapshot mechanism, fail-open, credited to
  feature-flow (MIT)), ending "Nothing calls the scan yet."
- `tests/fsm_flows/test_proof_tree.py` (new, 13 tests), `tests/fsm_flows/test_proof_floor.py`
  (new, 23 tests), regenerated `tests/INDEX.md` and `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh after the last code edit)

- `python -m pytest tests/fsm_flows/test_proof_tree.py -q -p no:cacheprovider`: `13 passed in
  5.34s`, exit 0. Covers: a snapshot sees a modified tracked file, a new untracked file and a
  deletion (`changes` == `[("A","new.py"), ("D","tests/test_app.py"), ("M","src/app.py")]`)
  and ignores a `.gitignore`d file (`blob(...,"ignored.txt") is None`); on a half-staged repo
  the `.git/index` bytes read just before and just after `snapshot` are equal and `head` is
  unchanged and equals `git rev-parse HEAD`; `blob` equals `git hash-object` and is `None` for
  a missing path; `diff_text(..., exclude=["pathly/"])` has `+++ b/src/app.py` and no
  `pathly/`, while `paths=["pathly/"]` has only the plan file; outside a repo, in `repo/src`
  (with real tree ids that do differ at the top), and with no `git` on `PATH`, `snapshot`,
  `head`, `blob` give `None` and `changes`/`diff_text` give `[]`/`""`. Also: the temp index is
  removed (a monkeypatched `tempfile.tempdir` is empty afterwards), a repo with no index file
  yet snapshots (and still has none), an index with an unmerged entry (`UU src/app.py`)
  snapshots with its bytes unchanged, no context lines at `unified=0`, and a `None` tree id
  gives an empty result.
- `python -m pytest tests/fsm_flows/test_proof_floor.py -q -p no:cacheprovider`: `23 passed in
  4.72s`, exit 0. One finding per category: `skip: tests/test_x.py: @pytest.mark.skip`;
  `suppress: src/app.py: return a + b  # noqa`; `empty-catch: src/app.py: except ImportError:
  pass`; `test-delete: tests/test_x.py: ...`; `threshold: pyproject.toml: fail_under = 60` (with
  `config`, as `[tool.coverage.report]` is guarded); `trivial-assert: tests/test_x.py: assert
  True`; `config: pytest.ini: ...`; `config: pyproject.toml: ...` for a
  `[tool.pytest.ini_options]` edit; `plan-edit: pathly/features/demo/USER_STORIES.md: ...`.
  Also: `allow=parse_allow(["skip"])` gives no finding; `@pytest.mark.skip  # noqa` written
  into `pathly/features/demo/notes.md` gives no finding; `may_change` returning true clears the
  `plan-edit`; a removed assertion gives `findings == []` and one warning `1 assertion line(s)
  removed, 0 added...`; `parse_allow(["nope"])` raises `ValueError` naming `nope` and the valid
  categories. Extra: `it.only(` is `skip` in `web/app.test.js` but `fit(data)` in `src/app.py`
  is nothing; `assert True` outside a test file is nothing; a `[project]` version edit is not
  `config`; Makefile only with a `make` verify command (plain or JSON argv); `conftest.py` only
  with a collection word; `package.json` only when a guarded key changes; scan outside a repo
  is empty.
- The ```check block: the same two commands, both exit 0 and print `passed` (above).
- Lint (the full chain from `commands.md`): exit 0. black `495 files would be left unchanged`;
  mypy `Success: no issues found in 281 source files`; file size `none new, none grown`; mirror
  reads OK; `All test INDEX.md files up to date.`; lint-imports `Contracts: 1 kept, 0 broken.`;
  bandit no findings; adapters OK; entry points OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0; the wheel lists `proof/tree.py` and
  `proof/floor.py`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2425 passed, 14 skipped in
  502.58s`, exit 0.
- An AST walk of `tree.py` and `floor.py` finds only stdlib imports and `from . import tree`.

**Decisions**

- `tree.py` has its own `_git` runner rather than `proof.command.run_command`: `run_command`
  merges stdout and stderr and decodes strictly with the locale. git warnings on stderr would
  land in the parsed tree ids and diffs, and one non-UTF-8 file in a diff would make the whole
  decode fail, so the scan would fail open on every diff with such a file in it (an easy way
  around the guard). `_git` keeps stdout alone and decodes with `surrogateescape`, as
  feature-flow does.
- `_git` drops `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and `GIT_COMMON_DIR` from the
  inherited environment, so `cwd=root` always names the repo (a value inherited from a git hook
  would otherwise point every call at another repo or index). It also passes
  `-c core.quotepath=off` so non-ASCII paths come back as text.
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
  before a file's first `@@`, so an added line `++ x` (printed `+++ x`) is still scanned, and
  the tab git adds after a name with a space is dropped. feature-flow reads names from any
  `+++ ` line and splits on whitespace.
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

**Shortcuts taken**

- A path that git still C-quotes with `core.quotepath=off` (one holding `"`, `\` or a control
  character) keeps its quotes in the diff headers, so it is not recognised as a test file for
  `FOCUSED` / `trivial-assert` / `count_assertions`. Every other pattern still applies. Worth
  unquoting if such paths ever show up.
- A file marked binary for diff (a `-diff` line in `.gitattributes`) shows no added lines, so
  its patterns are not scanned; `.gitattributes` is not a `config` file either. Passing `--text`
  would close that, but would put binary bytes into `diff_text`, which ticket 10 puts into
  prompts (argv cannot hold a NUL). Worth closing with a floor-only `--text` if an agent is ever
  seen doing it.
- `scan` fails open silently: when git cannot diff (or times out after 60 s), the report is
  empty and looks clean. Callers check both snapshot ids for `None` first (tickets 05/06 log a
  skip); a diff that fails between two good snapshots is not told apart.
- Each `tree` call runs its own `--show-toplevel` check (one extra git process per call).
  Cheap next to a snapshot; worth caching if a caller ever loops over many `blob` calls.

**For later tickets**

- Import as `from pathly_orchestrator.proof import floor, tree`. `tree.snapshot(root)` returns
  `None` outside a repo top, so store `None` and skip; `tree.changes/diff_text/blob/read` accept
  a `None` tree id and return empty/`None`.
- `floor.scan(root, base, after, allow=..., protected=[...], may_change=fn, config_commands=[...])`.
  Ticket 06 should pass `config_commands` from the `verify.*` settings so a `Makefile` counts
  when the project builds with make. Ticket 04's `may_change(path)` gets repo-relative POSIX
  paths (as git prints them).
- Ticket 03 can validate an allow list with `floor.parse_allow(list)` and use the
  `ValueError` text in the 400 body.
- `tree.blob(root, tree, path)` returns `None` both for an absent path and outside a repo;
  ticket 04's "current blob equals a window's after-blob" comparison should treat `None ==
  None` (both deleted) as explained only when both trees exist.
- The `task-edit` category is accepted by `parse_allow` and dropped by `allow`, but `scan`
  never produces it: tickets 05/06 add it themselves, after checking `allow`.
