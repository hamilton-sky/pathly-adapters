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
  `prompt` string (docs: hooks; the other fields are ignored).
- POST `{run_id, hook_secret, text}` to `/chief/human-messages` with
  `pathly_orchestrator.fsm_http_client._request_json` (it already sends the server secret), on
  `127.0.0.1` and the given port, with a short timeout.
- On success print one line, which Claude Code adds to the chief's context:
  `Pathly recorded this as human message <id>; cite it with cite=<id> when you relay an answer.`
  For the session's first message (kind `style_prompt`) print nothing.
- Always return 0, whatever happens (bad stdin, server down, 403): a hook failure must never
  block or alter the human's prompt. Run as `python -m pathly_hooks.chief_prompt`.

`POST /chief/human-messages` in a new `blueprints/chief/human.py` (added to the package's
`all_blueprints`): body `{run_id, hook_secret, text}`; 400 when `text` is not a non-empty string
of at most 64 KiB; 404 when the session is unknown or closed; 403 when sha256 of `hook_secret`
does not match the session's `hook_secret_hash` (compare with `hmac.compare_digest`); otherwise
`queries.chief.add_human_message` and 201 `{id, kind}`. The chief gate already refuses this route
to a chief token, so only the hook (which holds the secret file) can write here.

Living docs: `src/pathly_orchestrator/CLAUDE.md` lists the route and the hook; the hooks list in
`src/pathly_data/CLAUDE.md` if it enumerates `pathly_hooks` modules.

## Not in this ticket

- Checking citations when the chief answers: ticket 10.
- Codex capture: an open question in map.md; a codex chief has no hook.
- A console-script entry for the hook: not needed, it runs with `-m`.

## Done when

- `python -m pytest tests/comms_board/test_chief_human_messages.py -q -p no:cacheprovider` passes
  and covers: with a session opened through `open_chief` and a fake broadcaster, a POST with the
  secret from the session folder stores the first text as `style_prompt` and the second as
  `human`; a wrong secret is 403 and stores nothing; a closed session is 404; a 70 KiB text is
  400; a chief token on the route is 403; `chief_prompt.main` fed a stdin JSON `{"prompt": "use
  CSV"}` with `_request_json` replaced by a fake returns 0 and prints the id for a `human` reply;
  it returns 0 and prints nothing for bad stdin and for a raised connection error.
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
