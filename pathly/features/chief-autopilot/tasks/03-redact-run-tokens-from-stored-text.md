# Redact run tokens where Pathly writes text to its database

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/secret_scan.py (new), src/pathly_orchestrator/eventlog.py, src/pathly_orchestrator/db/queries/run_log.py, src/pathly_orchestrator/db/queries/comms_messages.py, src/pathly_orchestrator/supervisor/task_retry.py, src/pathly_data/core/skills/fragments/completion-report.md, tests/snapshots/, tests/db/test_secret_scan.py, tests/http_api/test_token_redact_writes.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/db/INDEX.md, tests/http_api/INDEX.md

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
  they are.
- `redact_run_tokens(conn, text) -> str`: replaces each with `[run token]`.
- `contains_secret_hash(text, sha256_hex) -> bool`: the same window for one hash (ticket 02).

Apply `redact_run_tokens` at the write chokepoints, not per route, so the agent's direct-DB
fallback is covered too:

- `src/pathly_orchestrator/eventlog.py::append_event`: every string value of the event (`summary`,
  `error`, `result`), before the insert;
- `src/pathly_orchestrator/db/queries/run_log.py::update_run_log_stdout` and
  `write_run_log_spawn`;
- `src/pathly_orchestrator/db/queries/comms_messages.py::post_message` (text and every stored text
  field) and the task completion write behind `/comms/tasks/complete` (find it from that route);
- `src/pathly_orchestrator/supervisor/task_retry.py`'s `fail_reason` writes (`retry_task`,
  `fail_task`, the escalation text).

Keep the scan cheap: skip text with no 43-character run. `eventlog.py` (382 lines) and
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
  found, and a random 43-character string is not; both env patterns; after a
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
