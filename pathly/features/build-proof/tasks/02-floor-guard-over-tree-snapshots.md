# Port the floor guard over git working-tree snapshots

Type: task
Status: open
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
