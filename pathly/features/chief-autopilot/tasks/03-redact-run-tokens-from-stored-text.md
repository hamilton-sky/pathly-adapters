# Redact run tokens from every text Pathly stores

Type: task
Status: open
Blocked by: —
Test first: yes

Spike S3: a headless goal-run agent's first command was `echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"`,
so its token sat in its output. Pathly stores agent output in several places, and a stored token
is usable by anyone who can read it until the run ends.

Add `runner/token_redact.py::redact_run_tokens(text: str, tokens: Iterable[str]) -> str`, which
replaces each given raw token with `[run token]`, and a caller-side helper that knows the raw
token of the spawn it handles (the spawn chokepoint has it: it minted it). Apply it where spawn
output becomes stored text:

- the `stdout_tail` the spawn host posts to `POST /runner/terminal/result`
  (`blueprints/runner/api_lifecycle.py`) and to `POST /db/invocation` (`db_api_invocation.py`),
  before anything parses or stores it;
- the `summary` of an `AGENT_DONE` written for that run (`terminal_reconcile._synthesize_agent_done_if_missing`
  and the agent's own, through the event append for a run-token caller);
- the `text` of a board post made with a run token (`/comms/post`): a token in the text is the
  caller's own, so redact the caller's token.

A token whose raw value Pathly no longer holds cannot be matched; also redact any
`PATHLY_RUN_TOKEN=<value>` or `PATHLY_RUN_TOKEN: <value>` pattern, whatever the value. Add one line
to the `completion-report` or `comms-post` fragment: never print environment variables. Living
docs: the run-token paragraph of `src/pathly_orchestrator/CLAUDE.md`, and name the known limit
(claude's own transcript under `~/.claude/projects/` is outside Pathly).

## Not in this ticket

- Revoking a token that was printed: tokens already end with their run.
- The raw token on `/events/spawn` (open carry-forward RRP-2b, needs a UI token).

## Done when

- `python -m pytest tests/runner_supervisor/test_token_redact.py tests/http_api/test_token_redact_routes.py -q -p no:cacheprovider`
  passes and covers: the helper replaces every occurrence and both env patterns; a
  `/runner/terminal/result` and a `/db/invocation` post whose tail holds the run's token store no
  copy of it (search the DB rows and the events); a synthetic `AGENT_DONE` summary with the token
  is redacted; a run-token `/comms/post` with its own token in the text stores `[run token]`.
- `python scripts/check_adapters.py` exits 0 (the fragment change rebuilt cleanly).

```check
$ python -m pytest tests/runner_supervisor/test_token_redact.py tests/http_api/test_token_redact_routes.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_adapters.py
exit 0
```

## Reference

- spike19-part-b-report.md § Surprises ("first command was echo")
- `src/pathly_orchestrator/db/queries/run_tokens.py`, `src/pathly_orchestrator/chief_cli.py::_redact` (the CLI's own redaction, for shape)

## Answer
