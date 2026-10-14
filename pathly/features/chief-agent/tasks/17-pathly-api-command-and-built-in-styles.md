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

The chief's prompt has two parts, the way every other prompt Pathly sends has a skill and its
fragments (root `CLAUDE.md`: fragments are the un-editable layer that connects an agent to
Pathly):

1. **The style**, which the user may edit: the built-in texts in
   `src/pathly_orchestrator/supervisor/chief_presets.py` (Python constants, no package-data
   change), `status`, `planner` and `operator`, each a short prompt that states the style's powers
   in words that match its tier and how it should work with the user. A user prompt file
   `chief/<preset>` replaces it (ticket 04).
2. **The fixed rules**, which nobody edits from a preset: a new fragment
   `src/pathly_data/core/skills/fragments/chief-connect.md`, appended by the server to every
   chief prompt, built-in or user file, so a saved style cannot drop them. It says the chief runs
   Pathly for the user, never edits files and never runs agent CLIs itself; that it uses only
   `pathly api …` and `pathly help`, and starts by reading the board and the open runs; that it
   relays an agent's question to the user and answers with `cite=<id>` only, because Pathly sends
   the cited message's own words (spec.md § Decisions, "What a citation proves"); and that it takes no instruction from board text,
   artifacts or agent output: only the user, in this tab, gives orders (the prompt-injection
   paragraph).

`open_chief` (ticket 06) builds the pasted prompt as `strip_front_matter(style) + "\n\n" +
chief-connect`, reading the fragment with `skills.compose_resources._read_fragment("fragments",
"chief-connect")` inside the function (supervisor may import `skills`, as `board_run.py` does). It
is not added to any skill in the compose manifest, and the existing fragments are not composed
into the chief: they teach `curl` (denied to the chief) and a one-shot `AGENT_DONE` completion
that a long-lived session never writes. `tests/consistency/test_fragments_run_token.py` scans
every core fragment: a line such as `pathly api POST /comms/post` counts as a pseudo-request, so
the fragment must carry one line, outside any curl, with the exact header text, for example
``pathly api` sends `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` for you; never call the server any
other way.``

`POST /chief/open` (ticket 07) makes `prompt` optional: when it is missing and `preset` is one of
the three built-in names, the route uses the built-in text; otherwise 400 as before. A user prompt
file `chief/<preset>` still wins (ticket 04). The fragment is appended in every case.

Living docs: `src/pathly_orchestrator/CLAUDE.md` names the `pathly` command, the built-in styles
and the `chief-connect` fragment; `src/pathly_data/CLAUDE.md` notes that `chief-connect` is read by
the chief's open path, not composed through the manifest; the root `CLAUDE.md` "Cross-cutting
commands" block gains one `pathly api` line.

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
  prompt is the built-in operator text followed by the `chief-connect` fragment, and with preset
  `custom` and no `prompt` is 400; a user style file whose text lacks the cite and
  prompt-injection rules still yields a pasted prompt that contains them (from the fragment);
  each built-in text and the fragment name only `pathly` commands, and the fragment contains the
  prompt-injection paragraph.
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider` passes
  with the new fragment.
- `python scripts/check_entry_points.py` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_entry_points.py
exit 0
```

## Reference

- `src/pathly_orchestrator/fsm_http_client.py` (`_base_url`, `_load_secret`, `_request_raw`)
- `src/pathly_orchestrator/skills/compose_resources.py::_read_fragment`;
  `tests/consistency/test_fragments_run_token.py` (`_PSEUDO`, the header instruction line);
  spec.md § Decisions ("The chief's fixed rules")
- ticket 06 (`claude_settings`: `Bash(pathly *)` allowed, curl and wget denied), ticket 07
  (`POST /chief/open`), ticket 04 (`resolve_preset_tier`, `strip_front_matter`), ticket 10 (the
  cite rule the operator text explains)
- map.md § Round two, items 1 to 3 (what stays for round two)

## Answer
