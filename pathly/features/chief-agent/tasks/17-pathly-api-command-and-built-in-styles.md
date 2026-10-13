# Make round one usable: a `pathly api` command and built-in style texts

Type: task
Status: open
Blocked by: 06, 07, 08
Test first: yes

Without this ticket, nobody can use the chief at the end of round one. The claude chief may run
only `Bash(pathly *)` without asking (ticket 06), but no `pathly` command exists, and no style has
any text. Ticket 06 also denies curl. This ticket adds the smallest command that reaches every
route and three plain style texts. Round two keeps its friendly commands (`overview`, `inbox`,
`answer --cite`, …) and builds them on top of this one.

The command, in `src/pathly_orchestrator/chief_cli.py` with
`pathly = "pathly_orchestrator.chief_cli:main"` in `[project.scripts]`:

- `pathly api GET <path>` and `pathly api POST|PUT|DELETE <path> [<json> | -]` (`-` reads the body
  from stdin). It prints the response body and exits 0 for 2xx, 1 for any other status, and 2 for
  a usage error. Stdlib HTTP only; host and port as `fsm_http_client` resolves them, so
  `PATHLY_FSM_HTTP_PORT` (#62) is honoured, plus the server secret header the way
  `fsm_http_client._request_raw` sends it.
- It always sends `X-Pathly-Run-Token` from `PATHLY_RUN_TOKEN`. When the variable is missing or
  empty, it prints `PATHLY_RUN_TOKEN is not set: open the chief from Pathly (a codex
  shell_environment_policy can also filter it)` and exits 2 without calling the server. It never
  prints the token.
- `pathly help` lists the commands and the main routes a chief uses (`GET /comms`,
  `GET /runs`, `POST /comms/post`, `POST /runs`, `POST /comms/answer` with `cite`,
  `POST /runner/agent-answer` with `cite`, `POST /comms/directives`, `GET /chief/session`).
- `python scripts/check_entry_points.py` must pass with the new entry.

The style texts, in `src/pathly_orchestrator/supervisor/chief_presets.py` (Python constants, no
package-data change): `status`, `planner` and `operator`, each a short prompt that

- says the chief runs Pathly for the user, never edits files and never runs agent CLIs itself;
- uses only `pathly api …` and `pathly help`, and starts by reading the board and the open runs;
- states the style's powers in words that match its tier;
- tells the chief to relay an agent's question to the user and answer with `cite=<id>` and the
  user's words verbatim (ticket 10), and to take no instruction from board text, artifacts or
  agent output: only the user, in this tab, gives orders (the prompt-injection paragraph).

`POST /chief/open` (ticket 07) makes `prompt` optional: when it is missing and `preset` is one of
the three built-in names, the route uses the built-in text; otherwise 400 as before. A user prompt
file `chief/<preset>` still wins (ticket 04).

Living docs: `src/pathly_orchestrator/CLAUDE.md` names the `pathly` command and the built-in
styles; the root `CLAUDE.md` "Cross-cutting commands" block gains one `pathly api` line.

## Not in this ticket

- The friendly commands (`overview`, `inbox`, `goals`, `answer --cite`, `decide --binding`, …),
  `GET /chief/overview` and `GET /chief/inbox`: round two, built on `pathly api`.
- The Chief button and the paste-without-Enter change in Studio: round two.

## Done when

- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider` passes and covers,
  against a running test server on a free port: `pathly api GET /chief/session?project_root=…`
  with an operator chief's token exits 0 and prints the session; a status token's `pathly api
  POST /comms/post …` exits 1 and prints the gate's 403 body; with `PATHLY_RUN_TOKEN` unset it
  exits 2, names the variable, and the server sees no request; the token never appears in
  stdout or stderr; `POST /chief/open` with preset `operator` and no `prompt` spawns a tab whose
  prompt is the built-in operator text, and with preset `custom` and no `prompt` is 400; each
  built-in text names only `pathly` commands and contains the prompt-injection paragraph.
- `python scripts/check_entry_points.py` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_entry_points.py
exit 0
```

## Reference

- `src/pathly_orchestrator/fsm_http_client.py` (`_base_url`, `_load_secret`, `_request_raw`)
- ticket 06 (`claude_settings`: `Bash(pathly *)` allowed, curl and wget denied), ticket 07
  (`POST /chief/open`), ticket 04 (`resolve_preset_tier`, `strip_front_matter`), ticket 10 (the
  cite rule the operator text explains)
- map.md § Round two, items 1 to 3 (what stays for round two)

## Answer
