# Record what the human types in a claude chief tab

Type: task
Status: open
Blocked by: 06, 07, 08
Test first: yes

The chief session's claude settings already run
`<python> -m pathly_hooks.chief_prompt --run-id <id> --secret-file <path> --port <port>` on every
UserPromptSubmit. Build both ends.

`src/pathly_hooks/chief_prompt.py` with `main(argv=None) -> int`:

- Parse `--run-id`, `--secret-file`, `--port`. Read the hook's JSON from stdin and take its
  `prompt` and `session_id` strings (docs: hooks; `session_id` is one of the common fields).
- POST `{run_id, hook_secret, text, session_id}` to `/chief/human-messages` with
  `pathly_orchestrator.fsm_http_client._request_json` (it already sends the server secret), on
  `127.0.0.1` and the given port, with a short timeout.
- On success print one line, which Claude Code adds to the chief's context:
  `Pathly recorded this as human message <id>; cite it with cite=<id> when you relay an answer.`
  For the session's first message (kind `style_prompt`) print nothing.
- Always return 0, whatever happens (bad stdin, server down, 403): a hook failure must never
  block or alter the human's prompt. Run as `python -m pathly_hooks.chief_prompt`.

`POST /chief/human-messages` in a new `blueprints/chief/human.py` (added to the package's
`all_blueprints`): body `{run_id, hook_secret, text, session_id, relayed?}`; 400 when `text` is
not a non-empty string of at most 64 KiB; 404 when the session is unknown or closed; 403 when
sha256 of `hook_secret` does not match the session's `hook_secret_hash` (compare with
`hmac.compare_digest`); 403 `{"error": "not this chief's claude session"}` when `session_id` is
missing or differs from the session's `cli_session_id` (ticket 06 started claude with that
`--session-id`); otherwise `queries.chief.add_human_message(..., relayed=bool(relayed))` and 201
`{id, kind}`. The chief gate already refuses this route to a chief token, so only the hook (which
holds the secret file) can write here.

What the session id proves, and what it does not: it binds a recorded prompt to the chief's own
claude process, so a hook running in any other session (one that picked up the settings file,
say) records nothing. It does not tell a typed prompt from a message another claude session
sends into the chief: that message arrives in the chief's own process, with the chief's session
id, and UserPromptSubmit fires on it (docs: hooks). Measure this on the installed claude: send
the open chief a message from a second local session and capture the hook's stdin. If anything
tells it apart from a typed prompt (a field in the hook input, or a fixed wrapper around
`prompt`), the hook sends `relayed: true` for it, and the server stores it as `relayed`, which
ticket 10 never accepts as a citation. If nothing does, the hook sends every prompt as typed. In
both cases, write what you found in `learnings.md` and update the cross-session line in map.md
§ Open questions.

Living docs: `src/pathly_orchestrator/CLAUDE.md` lists the route and the hook; the hooks list in
`src/pathly_data/CLAUDE.md` if it enumerates `pathly_hooks` modules.

## Not in this ticket

- Checking citations when the chief answers: ticket 10.
- Codex capture: an open question in map.md; a codex chief has no hook.
- Turning off messages from other sessions for the chief: not known to be possible; the
  measurement above only decides whether they can be labelled.
- A console-script entry for the hook: not needed, it runs with `-m`.

## Done when

- `python -m pytest tests/comms_board/test_chief_human_messages.py -q -p no:cacheprovider` passes
  and covers: with a session opened through `open_chief` and a fake broadcaster, a POST with the
  secret from the session folder stores the first text as `style_prompt` and the second as
  `human`; a wrong secret is 403 and stores nothing; a missing `session_id`, or one that is not
  the session's `cli_session_id`, is 403 and stores nothing; `relayed: true` stores kind
  `relayed`; a closed session is 404; a 70 KiB text is 400; a chief token on the route is 403;
  `chief_prompt.main` fed a stdin JSON `{"prompt": "use CSV", "session_id": "<uuid>"}` with
  `_request_json` replaced by a fake returns 0, sends that `session_id`, and prints the id for a
  `human` reply; it returns 0 and prints nothing for bad stdin and for a raised connection error.
  If the measurement found a marker for messages from other sessions, a stdin carrying it is
  sent with `relayed: true`.
- `python scripts/check_entry_points.py` exits 0.

```check
$ python -m pytest tests/comms_board/test_chief_human_messages.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_entry_points.py
exit 0
```

## Reference

- spec.md § Decisions ("Recording human messages"), § Interfaces
- map.md § Decisions so far (docs: hooks)
- `src/pathly_hooks/stop_telemetry.py` (an existing hook that always exits 0)
- `src/pathly_orchestrator/fsm_http_client.py` (`_request_json`, `_load_secret`, `DEFAULT_PORT`)

## Answer
