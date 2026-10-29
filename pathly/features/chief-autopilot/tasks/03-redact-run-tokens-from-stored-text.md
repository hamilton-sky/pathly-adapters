# Redact run tokens where Pathly writes text to its database

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/secret_scan.py (new), src/pathly_orchestrator/db/queries/fsm_events.py, src/pathly_orchestrator/db/queries/comms_artifacts.py, src/pathly_orchestrator/db/queries/comms_artifact_rows.py (new), src/pathly_orchestrator/db/queries/comms_edit.py, src/pathly_orchestrator/db/queries/run_log.py, src/pathly_orchestrator/db/queries/comms_messages.py, src/pathly_orchestrator/supervisor/task_retry.py, src/pathly_orchestrator/db/queries/comms_tasks.py, src/pathly_orchestrator/db/queries/comms_task_fail.py (new), src/pathly_orchestrator/http_server/blueprints/comms/tasks_status.py, scripts/file_size_baseline.txt, src/pathly_data/core/skills/fragments/completion-report.md, tests/snapshots/, tests/db/test_secret_scan.py, tests/http_api/test_token_redact_writes.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/db/INDEX.md, tests/http_api/INDEX.md

Spike S3: a headless goal-run agent's first command was `echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"`.
Its output reached `run_log.stdout`, which any reader of `GET /runs/<id>` (a chief included) sees.
The server stores only `sha256` of each token (`src/pathly_orchestrator/db/queries/run_tokens.py`),
and `AGENT_DONE` is posted without a token or written by the agent's own process
(`completion-report` fragment fallback to `eventlog.append_event`), so redaction cannot rely on
holding the raw token.

New `src/pathly_orchestrator/db/secret_scan.py` (layer `db/`, no internal imports beyond
`db.connection`):

- `find_run_tokens(conn, text) -> list[str]`: every 43-character window of `[A-Za-z0-9_-]`
  (`secrets.token_urlsafe(32)`'s length) inside a longer run is hashed and looked up in
  `run_tokens.token_hash` (any run, revoked or not), with one static query (`IN (SELECT value FROM
  json_each(?))`). Plus the values after `PATHLY_RUN_TOKEN=` and `PATHLY_RUN_TOKEN:`, whatever
  they are, but not a shell reference such as `$PATHLY_RUN_TOKEN` or `"$PATHLY_RUN_TOKEN"`
  (stored prompts in `run_log` contain those).
- `redact_run_tokens(conn, text) -> str`: replaces each with `[run token]`.
- `contains_secret_hash(text, sha256_hex) -> bool`: the same window for one hash (ticket 02).

Apply `redact_run_tokens` at the write chokepoints, not per route, so the agent's direct-DB
fallback is covered too:

- `src/pathly_orchestrator/db/queries/fsm_events.py::append_event`, the real event insert (some
  callers, such as `db_api_feature_detail.py`, call it directly, bypassing
  `eventlog.append_event`): every string value of the event (`summary`, `error`, `result`);
- `src/pathly_orchestrator/db/queries/run_log.py::update_run_log_stdout` and
  `write_run_log_spawn`;
- `src/pathly_orchestrator/db/queries/comms_messages.py::post_message` (text and every stored text
  field), the board-row insert in `src/pathly_orchestrator/db/queries/comms_artifacts.py`, the text rewrite in
  `src/pathly_orchestrator/db/queries/comms_edit.py`, and the task completion write behind `/comms/tasks/complete` (find it
  from that route);
- `src/pathly_orchestrator/supervisor/task_retry.py`'s `fail_reason` writes (`retry_task`, the
  escalation text), and the reason it passes to `fail_task`: redact before the call, because
  `fail_task` lives in `comms_tasks.py`, at its 400-line ratchet baseline.

Keep the scan cheap: skip text with no 43-character run. `comms_artifacts.py` is exactly 400
lines and not in the size baseline, so move code out of it (into `comms_artifact_rows.py`, re-exported) before adding the call. `eventlog.py` (382 lines) and
`comms_messages.py` (370) have room; if a file would pass 400, move code out first.

Add one line to `src/pathly_data/core/skills/fragments/completion-report.md`: never print
environment variables or tokens. Regenerate the golden snapshots under `tests/snapshots/` with the
repo's tool (see `tests/install_skills/test_compose.py`). Living docs: the run-token paragraph of
`src/pathly_orchestrator/CLAUDE.md`, naming the known limit (claude's own transcript under
`~/.claude/projects/` is outside Pathly).

## Not in this ticket

- The raw token on `/events/spawn` (open carry-forward RRP-2b, needs a UI token).
- The OTel span and the `STAGE_RESULT` broadcast, which are not stored text a chief can read.

## Done when

- `python -m pytest tests/db/test_secret_scan.py tests/http_api/test_token_redact_writes.py -q -p no:cacheprovider`
  passes and covers: a live and a revoked token, alone and inside a longer token-like run, are
  found, and a random 43-character string is not; both env patterns, and `$PATHLY_RUN_TOKEN` is
  left alone; a direct `fsm_events.append_event`, an artifact row and an edited post are redacted; after a
  `/runner/terminal/result`, a `/runner/event` `AGENT_DONE` and a direct `append_event` whose text
  holds a run's token, no row in `fsm_events`, `run_log` or `comms_messages` contains it; a task
  failure reason with a token is stored redacted.
- `python -m pytest tests/install_skills -q -p no:cacheprovider` passes (snapshots regenerated).

```check
$ python -m pytest tests/db/test_secret_scan.py tests/http_api/test_token_redact_writes.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/install_skills -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Run-token redaction"), review M4, M5, M6
- `src/pathly_orchestrator/chief_cli.py::_redact` (the CLI's own redaction, for shape)

## Answer

**Built**:
- `src/pathly_orchestrator/db/secret_scan.py` (new): `find_run_tokens`, `redact_run_tokens`,
  `redact_value` (every string inside a dict/list, same object back when nothing changed),
  `contains_secret_hash`, `REDACTED = "[run token]"`, `TOKEN_LENGTH = 43`. Imports nothing internal.
- `src/pathly_orchestrator/db/queries/comms_artifact_rows.py` (new): `insert_artifact` moved out of
  `comms_artifacts.py` (400 -> 362 lines), re-exported there (so `comms.py`, routes and tests keep
  importing it from `comms_artifacts`); title and summary redacted.
- Redaction at the chokepoints: `fsm_events.append_event` (whole event via `redact_value`, before
  `json.dumps`, and the projection hook gets the redacted dict), `run_log.write_run_log_spawn`
  (prompt, board context, stdin) and `update_run_log_stdout`, `comms_messages.post_message` (text,
  the JSON of options / context_refs / files, artifact_path, stage, lane, slug),
  `comms_edit.update_message_text`, `supervisor/task_retry.py` (`resolve_task_failure` redacts
  `reason` first, so `retry_task`, `fail_task`, the status line, the broadcast and the escalation
  all get clean text; `retry_task` redacts too, as its own write).
- `src/pathly_data/core/skills/fragments/completion-report.md`: one bullet, never print env vars or
  tokens. Six golden snapshots in `tests/snapshots/` regenerated (the ones composing that fragment).
- Tests: `tests/db/test_secret_scan.py` (14), `tests/http_api/test_token_redact_writes.py` (1);
  INDEX files regenerated. Docs: `src/pathly_orchestrator/CLAUDE.md` "Redact" bullet after
  "Carry", plus file-tree lines for `secret_scan.py` and `comms_artifact_rows.py`.

**Proof**:
- `python -m pytest tests/db/test_secret_scan.py tests/http_api/test_token_redact_writes.py -q -p no:cacheprovider`
  -> `15 passed`, exit 0. Covered: live and revoked token alone and inside a longer run
  (`x{live}abc-_Z and Q{revoked}_`), random `token_urlsafe(32)` not found; `PATHLY_RUN_TOKEN=` and
  `PATHLY_RUN_TOKEN:` values redacted, `$PATHLY_RUN_TOKEN`, `"$PATHLY_RUN_TOKEN"`,
  `${PATHLY_RUN_TOKEN:-}` and the `X-Pathly-Run-Token: $PATHLY_RUN_TOKEN` header left alone;
  direct `fsm_events.append_event` (nested strings too), `insert_artifact` row, a post and its
  edit, run_log writes; after `/runner/terminal/result`, `/runner/event` AGENT_DONE and a direct
  `eventlog.append_event`, no value of any `fsm_events`, `run_log` or `comms_messages` row holds
  the token; task failure reason redacted on both the retry and the escalate branch (fail_reason,
  status lines, escalation post).
- The test-only commit `b7c6e435` fails at collection (`No module named
  'pathly_orchestrator.db.secret_scan'`).
- `python -m pytest tests/install_skills -q -p no:cacheprovider` -> `419 passed, 2 skipped`, exit 0.
- Lint chain from commands.md: all green (black, mypy, check_file_size "none new, none grown",
  mirror reads, gen_test_index --check, lint-imports 1 kept, bandit, adapters, entry points).

**Decisions**:
- "The board-row insert in comms_artifacts.py" read as `insert_artifact` (the free-text
  title/summary insert). The legacy sentinel insert in `find_or_create_artifact_by_path` writes
  `[legacy artifact] <filename>` and was left alone, as was `update_artifact_summary` (not named).
- `/comms/tasks/complete`: `complete_task` writes only status and a timestamp; the one text it
  stores is the `Done: <task text>` status line via `post_task_status` -> `post_message`, which is
  now redacted. No change needed in `comms_tasks.py`.
- Env-pattern values are replaced in place (regex sub), not by `str.replace`, so a short value
  such as `abc` never redacts other occurrences of `abc`. A value starting with `$` or `[` (an
  earlier `[run token]`) is skipped, so redaction is idempotent; a backslash ends a value, so the
  JSON text of options/context_refs/files stays valid JSON.
- A database without a `run_tokens` table (raw test connections) answers "no tokens"; any other
  `OperationalError` is raised.

**Shortcuts taken**:
- A long URL-safe run of length L costs L-42 sha256 hashes and one query with that many values;
  fine for stdout tails, would matter for megabyte base64 blobs (then cap or chunk the windows).
- `post_message` scans each field separately (up to 8 prefilter regex searches, a query only for a
  field with a 43-character run). One joined scan would save queries if it ever shows up in timing.

**Review fixes**:
- Floor guard (round 1), `# noqa: F401` on the `insert_artifact` re-export in `comms_artifacts.py`:
  removed. The module now declares `__all__` with its public functions plus the two re-exports
  (`insert_artifact`, `insert_artifact_row`), so the re-export is used without any suppression
  comment (no star import of this module exists). The `comms_hydrate` noqa line predates this
  ticket and is unchanged. `git diff 2f24667b` outside the ticket file adds no `noqa`,
  `type: ignore`, `nosec` or skip marker. Re-run: full Lint chain exit 0 (mypy "no issues found in
  348 source files", lint-imports 1 kept), the Done when tests `15 passed` exit 0,
  `tests/install_skills` `419 passed, 2 skipped` exit 0. `comms_artifacts.py` is 379 lines.

**For later tickets**:
- 02: use `db/secret_scan.py::contains_secret_hash(text, sha256_hex)`; it is the same 43-character
  window test.
- Not covered (outside this ticket's footprint): `fail_task`'s own write from the
  `/comms/tasks/fail` route (reason stored as given; `comms_tasks.py` is at its baseline), the
  mirror replay `comms_hydrate.insert_message_row` / `insert_artifact_row`, and
  `update_artifact_summary`.

## Review findings (round 1, floor guard)

floor guard: the diff weakens the bar instead of meeting it
suppress: src/pathly_orchestrator/db/queries/comms_artifacts.py: from .comms_artifact_rows import insert_artifact  # noqa: F401
if a finding is intended, the ticket needs a line like: Floor: allow <category>

## Review findings (round 2, quality review)

Range reviewed: 2f24667b..a5d18053. $END is HEAD, so no later commits were left out. I read the ticket as it stood at the base commit and the round-1 `## Review findings` section on its own. I did not read `## Answer`.

Done when, re-run by me: `tests/db/test_secret_scan.py` with `tests/http_api/test_token_redact_writes.py` gave 15 passed, and `tests/install_skills` gave 419 passed, 2 skipped. Neither left files behind.

Inputs probed as a hostile caller (level 3):
- event string values via `append_event`
- run_log prompt, stdin and stdout
- every text field of `post_message`, and edited text
- artifact title and summary, on insert and on update
- task fail reasons from `task_retry`, `/comms/tasks/fail` and `/comms/tasks/status`
- the env pattern: spaces, quotes, `$` references, JSON escaping
- scan cost on a 1 MB single run: 0.67 s in memory. That is acceptable, but `post_message` runs the scan inside the write lock.

QUALITY
1. major src/pathly_orchestrator/http_server/blueprints/comms/tasks.py (`comms_tasks_fail`) and src/pathly_orchestrator/http_server/blueprints/comms/tasks_status.py: both routes pass the caller's `reason` straight to `fail_task`, which writes it unredacted into `comms_messages.fail_reason`. A token-holding agent that posts `/comms/tasks/fail` with the token in `reason` gets it stored, and `get_tasks` (`SELECT *`) hands it to any board reader, a chief included. Only the `task_retry` path redacts before calling `fail_task`. Fix: redact `reason` in both routes before `fail_task`, or move the `fail_reason` write out of `comms_tasks.py` and redact it there, so it is one chokepoint as the ticket intends. Add a route-level test.
2. major src/pathly_orchestrator/db/queries/comms_artifacts.py (`update_artifact_summary`): the insert path now redacts `summary`, but the overwrite does not. POST `/comms/artifacts/<id>/summary`, reached through `comms_summary.set_artifact_summary`, stores any caller-supplied summary, token included. Fix: redact `summary` in `update_artifact_summary`. The file is at 379 lines, so there is room.
3. minor src/pathly_orchestrator/http_server/blueprints/comms/tasks_status.py (`_audit_line`): this predates the diff, but it bites now. `reason[:80]` is cut before `post_message` redacts, so a bare token near the cut is stored as a fragment under 43 characters, and the window scan no longer matches it. Fix: redact `reason` before slicing. That falls out of finding 1 if the route redacts first.
4. minor src/pathly_orchestrator/db/queries/comms_messages.py: `_clean`/`_json` run inside `with _get_write_lock(conn)` (they are evaluated as INSERT parameters), so the hashing of a large message holds the global write lock. Fix: compute the redacted values before taking the lock.

REVIEW: FAIL

## Footprint change (round 2)

The quality review's findings 1 to 3 need files that were not in `Touches:`. With the person's OK of
2026-10-29 for footprint misses, `Touches:` now also names `comms_tasks.py`, a new
`comms_task_fail.py`, `tasks_status.py` and `scripts/file_size_baseline.txt`. The intended shape:
move `fail_task` out of `comms_tasks.py` (at its 418-line baseline) into `comms_task_fail.py`, which
redacts `reason` before the `fail_reason` write (one chokepoint for every route), and re-export it;
`tasks.py` (413, baseline) does not change. `tasks_status.py` redacts `reason` before it slices it.
