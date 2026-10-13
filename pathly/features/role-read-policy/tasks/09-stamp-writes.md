# Stamp author_role, author_run_id and author_source on every board write from the caller, not the body

Type: task
Status: resolved
Blocked by: 06, 08
Test first: yes

Add `src/pathly_orchestrator/runner/provenance.py` with `stamp(identity) -> dict` returning the
three provenance values (SPEC.md § C1):

- run identity → `author_role=identity.role`, `author_run_id=identity.run_id`,
  `author_source="token"`, whatever the body's `from` and `run_id` say;
- server-internal writer → `author_role="system"`, `author_source="system"` (a separate
  `system_stamp()`; never chosen from a body field);
- anonymous → `author_role=None`, `author_run_id=None`, `author_source="none"`.

Wire it in:

- `db/queries/comms_messages.py::post_message` accepts the three values (keyword arguments,
  default `None`) and inserts them.
- `http_server/blueprints/comms/messages_write.py` (`/comms/post`) computes
  `stamp(caller_identity(request))` and passes it. The file is 386 lines: keep the change to the
  call, with any logic in `provenance.py`. The `from_agent` and body `run_id` columns keep being
  written as today; only provenance ignores them.
- Server-internal writers pass `system_stamp()`: the `from_agent="system"` post inside
  `messages_write.py`, `supervisor/goal_verify.py`, `supervisor/task_retry.py`, and any other
  direct `post_message` caller in `supervisor/` or `runner/` (find them with
  `grep -rn "post_message(" src/pathly_orchestrator`; list them in the Answer).

An unknown or revoked token is stored as `author_source="none"` and logged, not refused (map.md,
Open questions).

## Not in this ticket

- The UI token (Studio posts stay `none` until RRP-2b).
- Refusing `binding` decisions by role: chief-agent CHF-4.

## Done when

- `python -m pytest tests/comms_board/test_comms_provenance.py -q` passes and covers: a post with
  a builder token and `from: "explorer"` is stored `author_role=builder`, `author_source=token`,
  `author_run_id=<builder run>`; a body `run_id` naming another run changes none of the three; a
  post with no token is `author_source=none`; a post with a revoked token is `none`; a
  `goal_verify` post is `system`/`system`.
- Every `post_message(` call under `src/pathly_orchestrator/supervisor` and `runner` passes a
  stamp (the test greps for it).

```check
$ python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C1 "The author role is not from_agent"
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py`,
  `db/queries/comms_messages.py` (`post_message`)
- Tickets 06 and 08 Answers

## Answer

(Updated in review round 1: the original Answer's "Left on the default" list and its Shortcuts no longer hold; the sections below describe the code as it is now.)

**Built**:
- Round 0 (unchanged, still true): `runner/provenance.py` (the git-provenance module that already existed) holds `stamp(identity)` and `system_stamp()`; `db/queries/comms_messages.py::post_message` takes `author_role` / `author_run_id` / `author_source` (default `None`, a missing source is stored `none`, never NULL); `http_server/blueprints/comms/messages_write.py` passes `**stamp(caller_identity(request))` on the post and `**system_stamp()` on the validate-at-write nudge; `supervisor/board_run.py` and `runner/comms_catalog.py` instruction strings carry the `X-Pathly-Run-Token` header.
- Round 1 (this fix): new `src/pathly_orchestrator/db/provenance_values.py` (`SOURCE_TOKEN/SYSTEM/LEGACY/NONE`, `AUTHOR_SOURCES`, `SYSTEM_ROLE`, `SYSTEM_AUTHOR`, `SYSTEM_PAIR`). `runner/provenance.py`: `stamp()` returns `none` and logs a warning naming the run for a run identity with an empty role; `system_stamp()` is built from the constants; new `post_system(conn, **fields)` = `post_message(..., **system_stamp())`. `db/queries/comms_messages.py`: `post_message` raises `ValueError` for an `author_source` outside `AUTHOR_SOURCES`. `db/queries/comms_artifacts.py`: `ensure_attached` passes `**SYSTEM_AUTHOR`, the sentinel INSERT binds `*SYSTEM_PAIR` (net 0 lines, file still exactly 400). `db/queries/comms_promote.py`: the copy carries the source's `author_*`. `board_mirror_hydrate.py`: `hydrate_board` runs `add_comms_provenance` (under the write lock) after the inserts. `comms/goals.py` (3 calls), `comms/project.py` (2), `comms/settings.py` (2): only their import lines changed, to `from pathly_orchestrator.runner.provenance import post_system as _post_message` (sizes 408 / 402 / 519, were 408 / 402 / 521). `code/query.py` (`_log_query`), `ops/_phase_board.py`, `comms/artifacts.py` (context-pull trail): `**stamp(caller_identity(request))`. `src/pathly_orchestrator/CLAUDE.md` (the provenance paragraph and the `db/` listing). Tests: `tests/comms_board/test_comms_provenance.py` (committed alone first as `3e06b02f`; 27 -> 93 tests) and the regenerated `tests/comms_board/INDEX.md`.

`post_message(` callers now (from `grep -rn "post_message(" src/pathly_orchestrator`):
- `**system_stamp()`: `supervisor/goal_verify.py`, `task_retry.py`, `scheduler.py`, `orchestrator_stage.py`; `fsm/engine_actions.py`; `messages_write.py` (nudge); `comms/_helpers.py`, `features.py` (2), `runs.py` (4), `control/_helpers.py`; and `runner/provenance.py::post_system` itself.
- Through `post_system` (alias `_post_message`): the seven in `comms/goals.py` / `project.py` / `settings.py`.
- Caller's token, `**stamp(caller_identity(request))`: `messages_write.py` (the post), `code/query.py`, `ops/_phase_board.py`, `comms/artifacts.py`.
- `**SYSTEM_AUTHOR` (db layer cannot import runner): `comms_artifacts.py::ensure_attached`.
- Left on the scan's allow-list (2 files): `comms_messages.py::answer_question` (a human answer in the UI, default `none`) and `comms_promote.py` (copies the source row's three values).
- Not a `post_message` caller: `db/queries/comms_hydrate.py` (dynamic `INSERT OR IGNORE`), allow-listed on the INSERT scan; `hydrate_board` now labels its pre-upgrade rows.

**Proof** (all run fresh after the last code edit):
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider` -> `93 passed`, exit 0.
- `python -m pytest tests/comms_board -q -p no:cacheprovider` -> `608 passed` (542 before), exit 0.
- Test-first: `3e06b02f` (the test file alone) ran `24 failed, 69 passed` against the old code. Each failed for its stated reason: `got ... 'token'` where `none` was expected (role-less stamp and role-less post, `(None, 'run-norole', 'token')`); `ImportError: cannot import name 'post_system'` (wrapper and promotion tests); `[(None, None, 'none')]` where all-`system` was expected (the 6 tests that drive the 7 frozen status posts); `[('code-intel', 'system', None, 'system')]` where `builder/token` or `none` was expected (code-query, record_phase and trail, 5 tests); `(None, None, None) == ('builder', None, 'legacy')` (hydrate); `DID NOT RAISE ValueError`; `ImportError: cannot import name 'provenance_values'`; the allow-list test listing the seven frozen-file calls; the wrapper-binding test (`{'_post_message': {'post_message'}}`); the hard-coded-literal scan listing `comms_artifacts.py:307-308` and `runner/provenance.py`. The 69 that passed are the unchanged round-0 tests, the scans' negative tests (they exercise the new scan code, which lives in the same test file) and a few controls.
- Allow-list still fails on a stale entry: adding `"runner/provenance.py"` to `_UNSTAMPED_ALLOW` made `test_the_allow_list_has_no_stale_entries` fail ("no unstamped post_message call left in: ['runner/provenance.py']"); reverted.
- commands.md: Build (`compileall`) exit 0; Smoke exit 0; Test (`tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/consistency/test_fragments_run_token.py -q -x -p no:cacheprovider`) -> `1073 passed, 2 skipped` (1007 before), exit 0; Lint: `black --check src/ tests/` 479 files unchanged, `check_file_size.py` "OK: 933 source files checked; 19 known over 400 lines, none new, none grown", `check_no_mirror_reads.py` OK, `gen_test_index.py --check` up to date (after `gen_test_index.py` regenerated `tests/comms_board/INDEX.md`), `lint-imports` 1 kept 0 broken.
- Also: `python -m pytest tests/dag_goals tests/fsm_flows tests/telemetry tests/code_intel tests/consistency -q -p no:cacheprovider` -> `783 passed, 10 skipped`, exit 0. `bandit -r src/ -ll -x src/pathly_data/` -> "No issues identified", exit 0, no `# nosec` added, every SQL string still a single static literal. `mypy src/ --ignore-missing-imports --no-strict-optional` -> "no issues found in 273 source files". `check_version_sync.py` OK.

**Decisions**:
- The wrapper is `post_system`, not `post_system_message`: the swap has to leave every frozen file's line count alone, and `from pathly_orchestrator.runner.provenance import post_system_message as _post_message` is 94 columns at the 8-space indent used in `goals.py` (90 at 4 spaces in `project.py`), so black would wrap it to three lines and each file would grow. `post_system` fits in 86. `settings.py` had a parenthesised two-name import; it became two one-line imports (519 lines, below its frozen 521; the baseline file is untouched).
- `stamp()` treats a run identity as verified only for a non-blank string role (`role.strip()`), so a whitespace role is `none` too. It returns the anonymous dict (`author_run_id` is also `None`), as the finding asked for `none`.
- The three agent-facing handlers all keep the caller's role; none is truly server-originated (the code-query line carries the caller's `target`/`role`, the phase row the body's `agent`/`phase`, the trail what the caller read). `_log_query` and `post_phase_to_board` read the Flask `request` directly instead of taking a parameter: `code/query.py` is 395 lines (5 to spare) and a signature change would have exploded a black-formatted one-line signature plus three call sites. Both are only reachable from a request handler. Outside a request context the best-effort post is skipped (the existing `except Exception` with a debug log), which is the same fail-quiet behaviour those helpers already had for any error.
- `hydrate_board` runs `add_comms_provenance` immediately after the inserts and before the best-effort re-embed (not after it), so the window in which hydrated rows have a NULL source is as short as possible; it is wrapped so hydration still never raises.
- `author_source` accepts `None` as "missing" (stored `none`); any other value, including `""`, outside `AUTHOR_SOURCES` raises `ValueError` before anything is written.
- Scan rules (test side): a `**` value must be `stamp(caller_identity(...))` (exactly), `system_stamp()` or the db constant `SYSTEM_AUTHOR`; an `author_source=` keyword counts only as a literal inside the allowed set, and then every other `author_*` keyword must be a literal too; an alias other than `_post_message`, `functools.partial(post_message)`, an assignment or `getattr` of it fail; a name bound only to `post_system` is stamped by construction (bound to both, it is raw). A separate scan bans a string literal for an `author_*` keyword or dict key anywhere in `src/` (the constants live in `db/provenance_values.py`). INSERT scan: `re.I`, `INSERT [OR x] INTO` and `REPLACE INTO`, bare / `""` / `[]` / backtick / schema-qualified names, `{}` tables, `+`-split literals, several statements in one string.

**Shortcuts taken**:
- The bypass scan is AST-by-name: it does not follow `importlib`, `__import__`, `eval` or a re-export under a new module. Worth upgrading only if such a pattern appears; the test would then need a runtime hook on `post_message` instead.
- `_log_query` / `post_phase_to_board` stamp from the ambient Flask `request`; a future non-request caller would post nothing. Upgrade: pass the identity in as a parameter once `code/query.py` is split.
- `answer_question` still stores `none` even when the request carried a token (a human UI answer, type `answer`, not withheld by any built-in policy); the upgrade is threading the stamp through that db function, natural once RRP-2b gives the UI a token.
- `promote_message` raises `ValueError` if the source row holds an `author_source` outside the set (only possible from a hand-edited BOARD.json hydrated before this round's validation existed); it does not sanitise it.
- `stamp()` logs a warning on every post of a role-less run (no de-duplication); a run with no role is a minting bug worth hearing about each time.

**Review fixes** (round 1, quality review):
1. Role-less token (major): fixed. `stamp()` returns `(None, None, 'none')` and logs a `WARNING` naming the run for a run identity whose role is `None`, empty or blank; `token` only for a non-empty role. Tests: three parametrised stamp cases with the log assertion, and a post with a role-less token stored `(None, None, none)` with `row_allowed(..., BUILTIN_DEFAULTS["reviewer"], None)` False (control: an explorer-token row is True).
2. Seven `none` status posts (major): fixed with `post_system` (`runner/provenance.py`) imported `as _post_message` in `comms/goals.py` (3), `project.py` (2) and `settings.py` (2): import lines only, no call site changed, no file grew. The allow-list lost those three files (now 2 entries: `answer_question`, `promote_message`) and the stale-entry test still fails on a stale entry (shown above). Six route tests drive all seven posts and assert `system/None/system` (goal stop, goal run, goal decompose, project decompose, project consultation, consolidate with both its dedup line and its reflector line); `check_file_size.py` is clean.
3. Scans (minor): tightened as listed under Decisions, each with a negative test that feeds the variant to the scan: lower / mixed case INSERT, `REPLACE INTO`, `INSERT OR REPLACE`, `""`/`[]`/backtick quoting, `main.` and `"main"."..."` qualification, no column list, a `+`-split literal, a qualified dynamic table; an aliased import, `partial`, assignment, module-attribute alias, `getattr`, a callback argument; body-derived `author_source`, a literal outside the set, a body-derived role beside a literal source, `stamp(CallerIdentity(...))`, `stamp(identity)`, `**{...}`, `**dict(...)`; plus sound controls that must pass. Every real file in `src/` passes the stricter scans with no new allow-list entry.
4. Hydrate (minor): fixed. `hydrate_board` calls `add_comms_provenance(conn)` after the inserts. Test: a snapshot row with no `author_*` keys lands `('builder', None, 'legacy')` and is withheld from the reviewer; a row that already carries `explorer/run-x/token` keeps it.
5. Caller-content handlers (minor): fixed, none kept as `system`. `/code/query` log row, `/record_phase` row and the context-pull trail are stamped from `stamp(caller_identity(request))`. Tests (5): a builder token with a body role/agent of `explorer` -> `builder/run-builder/token` for each, and an anonymous caller -> `none` for the code-query and record_phase rows.
6. Promotion (minor): fixed. The copy takes the source's `author_role`, `author_run_id`, `author_source`. Test: token-stamped and `system` decisions each keep their three values over feature -> project -> global (two hops).
7. Constants (minor): fixed. `db/provenance_values.py` holds `AUTHOR_SOURCES` and the `system` constants once; `runner/provenance.py`, `ensure_attached`, the sentinel INSERT and `post_message` import them; `post_message` rejects an unknown source. Tests: `ValueError` for `admin`, `""`, `Token` with no row written; a missing source still stored `none`; the module's set equals the set pinned in the test; no author string literal remains in `src/` outside the constants module.

**For later tickets**:
- Ticket 10 (acceptance): unchanged from round 0 for `POST /comms/post` (`X-Pathly-Run-Token` + `from: "explorer"` -> `author_role=<the run's role>`, `author_run_id=<run_id>`, `author_source=token`; no header -> `author_source=none`, `author_role=NULL`). New: a run token minted with no role is stored `none`, so an acceptance run must mint with a role. The CLAUDE.md paragraph for this is in place; extend rather than duplicate it.
- Any new `post_message` caller must pass `**system_stamp()` (server text), `**stamp(caller_identity(request))` (text the caller supplies), or come through `post_system`; or be added to `_UNSTAMPED_ALLOW` in `tests/comms_board/test_comms_provenance.py` with a reason. A new `INSERT`/`REPLACE INTO comms_messages` must name `author_source`; an aliased import of `post_message` fails the bypass scan.
- Studio UI posts stay `none` until RRP-2b, as planned. With the policy in `enforce`, the seven lifecycle status lines are now `system`, so the reviewer, tester and anonymous walls (which withhold only `none` and builder rows) let them through; `answer` rows from the UI are `none`.
- `comms_artifacts.py` is exactly 400 lines: the next change there must split it first.

## Review findings (round 1, quality review)

QUALITY
1. major src/pathly_orchestrator/runner/provenance.py: A live token whose run has no role is stamped as a verified row with no role, and the read policy lets it through. `stamp()` returns `author_role=None, author_run_id=<run>, author_source="token"` whenever `identity.kind == "run"`. `terminal_identity._spawn_role` is documented to return `None` when it cannot resolve a role, and `mint_run_token` accepts `role=None`. Run: a role-less token posting a `discovery` is stored as `(None, run-norole, token)`, and `row_allowed(row, BUILTIN_DEFAULTS["reviewer"], None)` returns True. The reviewer wall only withholds `author_source == 'none'` or a role in `exclude_authors`, so a role-less run's rows are visible to the reviewer: a fail-open default on the boundary this ticket owns. Change: in `stamp()`, treat a run identity with a falsy role as `none` and log it (or stamp `token` only when the role is non-empty). Add a test.
2. major src/pathly_orchestrator/http_server/blueprints/comms/{goals,project,settings}.py (plus the allow-list in `tests/comms_board/test_comms_provenance.py`): Seven server-written posts are left on the `none` default. All seven are `from_agent="system"`, `type="status"` goal and board lifecycle lines. SPEC C1 says server-internal writers are stamped `system` by the code path. The "size-frozen" reason does not hold: the ratchet only forbids growth. Changing each function-local `import ... post_message as _post_message` line to import a stamped wrapper (say `post_system_message` in `runner/provenance.py`) adds no lines. The ten other `system` posts in `http_server` are already stamped. Once the read wall is in `enforce`, these rows are `status` rows with source `none`, so they are withheld from reviewer, tester and the anonymous policy regardless of author, and counted as `unverified` withheld rows in C7, which pollutes the signal P6's soak and C0 depend on. Change: stamp them `system` now with a size-neutral edit (no ticket owns a follow-up).
3. minor tests/comms_board/test_comms_provenance.py: the scans can be fooled. The call scan matches only the names `post_message` and `_post_message`: an aliased import, a module attribute alias, `getattr` and `functools.partial` are unseen. `_passes_stamp` accepts any `author_source=<expr>`, including a body-derived value, and `**<anything>stamp(...)`, including `stamp(CallerIdentity(role=data["from"]))`. `_INSERT` is case-sensitive: lowercase `insert into comms_messages`, quoted or `main.` names, `REPLACE INTO` and a split string literal are missed. Change: compile `_INSERT` with `re.I`, allow `REPLACE`, quoted and qualified table names, require the stamp value to be a call to `stamp`/`system_stamp` or a literal, and fail on any import of `post_message` with an alias.
4. minor src/pathly_orchestrator/db/queries/comms_hydrate.py (`_insert_snapshot_row`): hydrated rows from a `BOARD.json` made before the upgrade keep a NULL `author_source` and NULL role; `row_allowed` and the SQL predicate show such a row to the reviewer (a NULL source is not `none`), until the next server start relabels it `legacy`. 08's learnings said to drive every insert path. Change: run `add_comms_provenance(conn)` at the end of `hydrate_board`, or default a missing source, and cover it with a test.
5. minor src/pathly_orchestrator/http_server/blueprints/code/query.py, `ops/_phase_board.py`, `comms/artifacts.py`: request handlers that write rows whose content is the caller's, stamped `system`. The `/code/query` log row is a `discovery` containing the caller-chosen `target` and `role`, written even for an unauthenticated caller. The `/record_phase` row takes its `from_agent` and `phase` from the body. The context-pull trail records what a builder read. A `system` discovery or status passes the reviewer wall, so a builder's activity trace becomes visible to the reviewer. Change: stamp these from `stamp(caller_identity(request))` so they keep the caller's role, or record why `system` is deliberate.
6. minor src/pathly_orchestrator/db/queries/comms_promote.py: the promoted copy is stored as `none`, dropping the source row's provenance. SPEC C8 ("provenance before promotion") needs `author_source in {token, system}`, so a feature->project->global chain would be refused on the second hop. Change: copy the source row's `author_*` onto the promoted row, or stamp it from the calling token.
7. minor src/pathly_orchestrator/db/queries/comms_artifacts.py and comms_messages.py: `ensure_attached` and the sentinel INSERT hard-code `'system','system'`, a second copy of `system_stamp()`. `post_message` also accepts any `author_source` string. Change: put the `system` constants and the `{token, system, legacy, none}` set in `db/` and import them from `runner/provenance.py` (runner may import db), and reject unknown values.

Checked and sound: in `/comms/post`, `**stamp(caller_identity(request))` is the only source of the three author columns; body `author_role`, `author_source`, `author_run_id`, `role`, `run_id` stored `(None, None, none)`; header variants and malformed tokens gave `none`; unknown and revoked tokens stored `none` and logged; `ui` identity is `none`; `post_message` stores a missing source as `none`, never NULL. `answer_question` (type answer) and promoted copies (decision, constraint) are not withheld by any built-in policy.

REVIEW: FAIL
