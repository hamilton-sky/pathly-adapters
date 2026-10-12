# Stamp author_role, author_run_id and author_source on every board write from the caller, not the body

Type: task
Status: open
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

**Built**: `src/pathly_orchestrator/runner/provenance.py` gained `stamp(identity)` and `system_stamp()` (the module already existed: it holds the git per-stage provenance; the new functions are appended and its docstring says so). `db/queries/comms_messages.py::post_message` takes `author_role` / `author_run_id` / `author_source` (default `None`) and inserts them. `http_server/blueprints/comms/messages_write.py` passes `**stamp(caller_identity(request))` on the main post and `**system_stamp()` on the validate-at-write nudge (386 -> 390 lines). Every server-internal `post_message` caller listed below passes `**system_stamp()`. The sentinel `INSERT INTO comms_messages` in `db/queries/comms_artifacts.py` now sets `author_role`/`author_source` (`system`). `supervisor/board_run.py` and `runner/comms_catalog.py` instruction strings carry the `X-Pathly-Run-Token` header. New `tests/comms_board/test_comms_provenance.py` (committed alone first as `7428f7f0`), regenerated `tests/INDEX.md` and `tests/comms_board/INDEX.md`, one paragraph in `src/pathly_orchestrator/CLAUDE.md` (under "Per-stage git provenance").

Every `post_message(` caller found by `grep -rn "post_message(" src/pathly_orchestrator` (line numbers are those before this change):
- `runner/`: none.
- `supervisor/`, `system_stamp()`: `goal_verify.py:102`, `task_retry.py:172`, `scheduler.py:65`, `orchestrator_stage.py:95`.
- `fsm/engine_actions.py:55`, `system_stamp()`.
- `http_server/blueprints/comms/messages_write.py:252` (nudge) `system_stamp()`; `:274` (the post) `stamp(caller_identity(request))`.
- `http_server`, `system_stamp()` (server-written status/lifecycle text): `comms/_helpers.py:202` (task transitions), `comms/features.py:135,274`, `comms/runs.py:67,159,191,289`, `comms/artifacts.py:236` (context-pull trail), `control/_helpers.py:99`, `ops/_phase_board.py:41`, `code/query.py:187`.
- `db/queries/comms_artifacts.py:297` (`ensure_attached`), literals `author_role="system", author_source="system"` (the db layer cannot import runner); its sentinel `INSERT` (`:240`) the same.
- Left on `post_message`'s default (`none`), on the test's commented allow-list: `comms/goals.py:72,248,334`, `comms/project.py:189,332`, `comms/settings.py:420,450` (all three files are over 400 lines and frozen, so a stamp argument would fail the size ratchet), `db/queries/comms_messages.py:246` (`answer_question`, a human in the UI) and `db/queries/comms_promote.py:150` (the promoted copy of a decision/constraint).
- Not a `post_message` caller: `db/queries/comms_hydrate.py` (dynamic `INSERT OR IGNORE INTO {table}` of a whole BOARD.json row, author columns included; a row from a pre-upgrade export has NULL and the startup backfill marks it `legacy`, which is what it is). On the INSERT scan's allow-list with that reason.

**Proof**:
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider` -> `27 passed`, exit 0. It covers: builder token + `from: "explorer"` -> `("builder", "run-builder", "token")` with `from_agent` still `explorer`; a body `run_id` naming another run changes none of the three (and the old `run_id` column still holds the body value); no token -> `(None, None, "none")`; body `run_id` without a token -> `none`; revoked token -> `none` and an info log line; unknown token -> `none`, not refused; `goal_verify` escalation, `task_retry` escalation, scheduler status, the `/comms/post` nudge, the artifact sentinel and `ensure_attached` messages -> `("system", None, "system")`; `post_message` with no stamp -> `none`, never NULL; a battery of insert paths leaves 0 rows with NULL `author_source`; `stamp`/`system_stamp` unit cases (`ui` kind -> `none`); `runner/provenance.py` imports nothing from `http_server`/`flask`; the board-run prompt and the catalog channel name the header.
- The same file's scans: every `post_message(` under `supervisor/` and `runner/` passes a stamp (AST scan, requires at least 4 calls so it cannot go blind); every call in `src/pathly_orchestrator` is stamped or on the allow-list, and the allow-list has no stale entry; every string literal `INSERT [OR x] INTO comms_messages` contains `author_source` and the only dynamic-table insert is the allow-listed hydration one; the scan sees exactly the two real inserts.
- Test-first: `7428f7f0` (the test file alone) ran `22 failed, 3 passed` (25 tests then): `ImportError: cannot import name 'stamp'` for the stamp tests and `(None, None, None) == (..., 'token'/'none'/'system')` for the writer tests (rows were written, columns NULL). Mutation check after the fix: removing `**system_stamp()` from `task_retry.py` -> 3 failed; removing `**stamp(caller_identity(request))` from `messages_write.py` -> 4 failed; removing `'system'` from the sentinel INSERT -> 2 failed; each restored.
- `python -m pytest tests/comms_board -q -p no:cacheprovider` -> `542 passed`, exit 0.
- commands.md Build (compileall) exit 0; Smoke exit 0; Test (`tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/consistency/test_fragments_run_token.py -q -x -p no:cacheprovider`) -> `1007 passed, 2 skipped` (980 before + 27 new), exit 0; Lint: `black --check src/ tests/` 478 files unchanged, `check_file_size.py` OK (932 files, none new, none grown; `comms_artifacts.py` is exactly 400), `check_no_mirror_reads.py` OK, `gen_test_index.py --check` up to date, `lint-imports` 1 kept 0 broken.
- Also run: `tests/dag_goals tests/fsm_flows tests/telemetry tests/code_intel tests/consistency` -> `783 passed, 10 skipped` (the supervisor, fsm, phase-board and code-query writers I touched live there). `bandit -r src/ -ll -x src/pathly_data/` -> "No issues identified", no `# nosec` added. `mypy src/ --ignore-missing-imports --no-strict-optional` -> no issues in 272 files.

**Decisions**:
- The ticket says "Add `runner/provenance.py`"; the file already existed (git stage provenance, `record_stage_provenance`, used by `api_lifecycle.py`). I appended `stamp`/`system_stamp` there rather than inventing another name, because the ticket, `IMPLEMENTATION_PLAN.md` and the chief-agent Smoke (`import pathly_orchestrator.runner.provenance`) all name that path. It imports nothing from `http_server`: `stamp(identity)` reads `identity.kind/.role/.run_id` by attribute.
- `post_message` stores `author_source or "none"`. The ticket says the keyword defaults to `None`, which it still does; what is inserted for a missing source is `none`, not NULL. Reason: ticket 08's backfill runs on every start and relabels any NULL `author_source` as `legacy`, so a writer I (or a later ticket) forget would hide as `legacy`. With this, a forgotten writer shows up as `none`, which is also the fail-closed value.
- Rule for who gets which stamp: text the agent supplies through `/comms/post` -> the caller's token identity; text the server composes itself (lifecycle statuses, gate escalations, the context-pull trail, phase markers, the code-query log) -> `system`, even when it describes an agent's action. The alternative (stamp those with the request's token) would need a DB lookup per request and a request object in helpers that have none.
- `stamp()` returns `none` for any identity that is not `kind == "run"`, including the reserved `ui` kind: the UI token is RRP-2b.
- An unknown or revoked token is stored as `none` and logged: `caller_identity` (ticket 06) already logs it at info with the remote address, so no new logging; a test pins the log line.
- Ticket 07 handed me the two instruction strings outside `core/`, so I edited them (the person running the flow allowed it): `supervisor/board_run.py` (the prompt's `POST http://127.0.0.1:8765/comms/post` line now says "with the header X-Pathly-Run-Token: $PATHLY_RUN_TOKEN and a JSON body", and the artifact paragraph says "and send the same header"; edited in place, the file stays at its frozen 490 lines) and `runner/comms_catalog.py` (the "To list all" and "To read one" lines gain "with the header `X-Pathly-Run-Token: $PATHLY_RUN_TOKEN`" / "with the same header"). No test or snapshot pinned those strings, so none changed; two new tests pin them.
- Scans are AST-based (string literals, f-strings rendered with `{}`), so multi-line SQL and `_post_message` aliases are seen. The allow-lists carry a reason per entry and each fails if it goes stale, so they can only shrink.
- Doc sync: one paragraph in `src/pathly_orchestrator/CLAUDE.md` where `runner/provenance.py` is described, because its "Per-stage git provenance" description became incomplete. Ticket 10 still owns the wider comms-board doc update.

**Shortcuts taken**: Seven `post_message` calls (`comms/goals.py` x3, `comms/project.py` x2, `comms/settings.py` x2) are server lifecycle status posts that should be `system` but are stored `none`: all three files are over 400 lines and frozen by `scripts/check_file_size.py`, so even one added line fails CI. They work as `none` (fail closed, visible, never `legacy`). It stops being right when the policy starts withholding `none` rows of an excluded type from a walled role, since a `status` the server wrote would then be hidden from a reviewer. Worth upgrading when any of those files is split under 400 lines: add `**system_stamp()` and delete its allow-list entry (the stale-entry test then forces it). `answer_question` and `promote_message` also store `none` even when the request carried a token (their rows are human answers and decision/constraint copies, which no built-in policy withholds); threading the stamp through the two db functions is the upgrade, natural once RRP-2b gives the UI a token. `post_message` does not validate `author_source` against `token|system|legacy|none`.

**For later tickets**:
- Ticket 10 (acceptance): `POST /comms/post` with `X-Pathly-Run-Token: <token from TERMINAL_SPAWN>` and `from: "explorer"` is stored `author_role=<the run's role>`, `author_run_id=<run_id>`, `author_source=token`; with no header it is `author_source=none`, `author_role=NULL`. `from_agent` and the body `run_id` column are unchanged. The CLAUDE.md paragraph for this is already in place; extend rather than duplicate it.
- Any new `post_message` caller must pass `**system_stamp()` (server text) or `**stamp(identity)`, or be added to `_UNSTAMPED_ALLOW` in `tests/comms_board/test_comms_provenance.py` with a reason; a new `INSERT INTO comms_messages` must name `author_source`. Both are enforced by that test.
- Studio UI posts stay `none` until RRP-2b, as planned.
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
