# Record what the human types in a claude chief tab

Type: task
Status: resolved
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

**Built**

- `src/pathly_hooks/chief_prompt.py` (new): `main(argv=None) -> int`, always 0. Parses `--run-id`,
  `--secret-file`, `--port` (a bad argument is a `ValueError` the catch-all turns into exit 0),
  reads stdin as UTF-8 bytes (`sys.stdin.buffer` when there is one), takes `prompt` and
  `session_id` (both non-empty strings or it sends nothing), reads the secret file, and posts
  `{run_id, hook_secret, text, session_id}` (plus `relayed: true`, below) with
  `fsm_http_client._request_json("POST", "/chief/human-messages", ..., host="127.0.0.1", port=<port>,
  timeout=5.0)`. It prints the cite line only for a reply of kind `human` with an integer id;
  `style_prompt` and `relayed` replies, odd replies and every exception print nothing.
- `src/pathly_orchestrator/http_server/blueprints/chief/human.py` (new) and `chief/__init__.py`
  (`all_blueprints` gains it): `POST /chief/human-messages`, in the order the ticket gives: 400 for a
  body that is not an object or a `text` that is blank, not a string, invalid Unicode (a lone
  surrogate) or over 64 KiB in bytes; 404 for a `run_id` that is not a string, unknown or closed;
  403 `bad hook secret` when sha256 of `hook_secret` is not `hook_secret_hash`
  (`hmac.compare_digest` on bytes; no stored hash never matches); 403
  `{"error": "not this chief's claude session"}` when `session_id` is missing or not the session's
  `cli_session_id` (a session with none, such as codex, never matches); else
  `add_human_message(conn, run_id, session["project_root"], text, relayed=bool(relayed))` and 201
  `{id, kind}`. No change to `chief_routes.py`/`chief_fields.py`: the route is not in
  `ROUTE_ACTIONS`, so the gate already answers a chief token 403 (`action: None`), and a route
  that is not listed needs no `ROUTE_FIELDS` entry (the tables test walks only listed routes).
- `tests/comms_board/test_chief_human_messages.py` (new, 45 tests: the route cases and the hook
  cases the ticket lists), `test_chief_prompt_hook.py` (new, 33 tests: the hook's edge cases and two
  real-process tests), `chief_human_support.py` (new: sessions through `open_chief` with a fake
  broadcaster, fixtures, `FakeServer`). Three files because black takes the dense version of the
  one file the ticket names to 640 lines, over the 400 limit. The first two were committed with the
  support file as `d717a8a` `test(chief-agent): 09 failing test`; the final file adds one test.
  `tests/INDEX.md` and `tests/comms_board/INDEX.md` regenerated.
- Living docs: root `CLAUDE.md` (the `chief/` line of the blueprint domain map),
  `src/pathly_orchestrator/CLAUDE.md` ("Chief endpoints": the route, a "Human messages" bullet
  that also describes the hook and the measurement; the deny-by-default example list; the package
  tree). `src/pathly_data/CLAUDE.md` does not enumerate `pathly_hooks` modules (it only describes
  how the installer writes the Stop hook), so it is unchanged.
- `learnings.md` (three lines) and `map.md` (one Decisions line, and the measurement added as
  lines under the existing cross-session bullet of Open questions; the floor guard allows only
  appended lines in `map.md`, so the old words of that bullet stay and the added lines say what
  was measured).

**The measurement** (installed claude 2.1.304; scratch dirs and a throwaway settings file under the
scratchpad, `/tmp/claude-0/-home-claude-pathly-adapters/5223161d-7afa-5239-b776-b281c8303b1d/scratchpad/xsession09/`,
a few cents on `--model haiku`; my own session's `CLAUDE_CODE_MESSAGING_*` variables were removed
from the children's environment)

- Receiver: the chief's own flags (`--tools Bash,Read,Glob,Grep --settings <file> --mcp-config <empty>
  --strict-mcp-config --session-id <uuid> --name chiefrecv09`) with a hook that appends its raw
  stdin to a file; once as `claude -p --input-format stream-json` kept open, once as an interactive
  tab in a pty. Sender: a second `claude -p --allowedTools "SendMessage ListAgents"` told to send
  `RELAYED-TEST-09 hello from another session` to the receiver.
- **With `--restricted` (the chief's real start): the receiver cannot be messaged.** Its debug log says
  `[uds-messaging] Skipped: restricted session`; no `messagingSocketPath` in
  `~/.claude/sessions/<pid>.json`; the sender's `ListAgents` did not list it ("No agent named
  'chiefrecv09' is reachable"); `SendMessage` to its would-be `uds:/tmp/cc-socks/<pid>.sock` failed
  with ENOENT. The hook fired once, for the typed prompt.
- **Without `--restricted` (`--setting-sources local`), in both `-p` and the interactive tab: the message
  is delivered and tells itself apart.** The hook ran for the typed prompt with `"prompt":
  "TYPED-PROMPT-1 ..."`, and for the other session's message with `"prompt":
  "<cross-session-message from=\"uds:/tmp/cc-socks/952.sock\" from-name=\"sender09\"
  from-mode=\"prompting\">\nRELAYED-TEST-09 hello from another session\n</cross-session-message>"`.
  The other hook-input fields were the same keys and values in both (`session_id` (the receiver's own),
  `transcript_path`, `cwd`, `scratchpad_dir`, `prompt_id`, `permission_mode`, `hook_event_name`,
  `session_title`). So the only marker is the wrapper around `prompt`, and the hook sends `relayed: true`
  when `<cross-session-message` (a regex with a word boundary) is anywhere in the prompt. It is a second
  line of defence on this version, since a restricted chief cannot be messaged.

**Proof** (each run fresh, after the last edit to code or tests; the docs, map and learnings were
edited afterwards)

- Test first: at `d717a8a` `python -m pytest tests/comms_board/test_chief_human_messages.py -q -p
  no:cacheprovider` failed at collection with `ImportError: cannot import name 'chief_prompt' from
  'pathly_hooks'` (the module did not exist), the right reason.
- `python -m pytest tests/comms_board/test_chief_human_messages.py -q -p no:cacheprovider` -> `45 passed in
  8.76s`, exit 0 (prints `passed`). Both new test files on Python 3.12 and on the 3.13 venv: `78 passed`
  each. They cover every Done-when case: the first text `style_prompt` and the second `human`
  (checked in the table too, with the stored `project_root`); a wrong, empty, null, numeric, extended
  or upper-cased secret and a missing secret key are 403 and store nothing; a missing, empty, numeric,
  list or foreign `session_id` is 403 with the exact error and stores nothing; `relayed: true` stores
  `relayed`; a closed session, an unknown run id and a list run id are 404; a 70 KiB text is 400 and
  exactly 64 KiB is stored; a chief token on the route is 403 at status, planner and operator
  (`action: None`, `allowed` present, nothing stored); `chief_prompt.main` fed `{"prompt": "use CSV",
  "session_id": "<uuid>"}` with `_request_json` replaced returns 0, sends that `session_id` and the
  secret, host `127.0.0.1`, the port and a timeout of at most 10 s, and prints
  `Pathly recorded this as human message 7; cite it with cite=7 when you relay an answer.`; it returns 0
  and prints nothing for seven kinds of bad stdin and for a raised `ConnectionRefusedError`; a stdin
  carrying the wrapper is sent with `relayed: True`.
- `python scripts/check_entry_points.py` -> exit 0 (no entry point was added; the hook runs with `-m`).
- Real hook, real server, real process: `test_the_written_hook_command_records_over_http` takes the
  command `open_chief` wrote into `settings.json`, runs it four times as a subprocess against a
  `werkzeug` server thread, and sees rows `style_prompt`, `human`, `relayed` (the foreign
  `session_id` stored nothing) and the cite line on stdout only for the `human` one. A throwaway
  script (scratchpad `b09/real_claude.py`) then ran the installed claude itself with the chief's exact
  argv (`--restricted --settings <that file> --session-id <uuid>` plus `-p`) against such a server:
  turn 1 (the style prompt) -> `POST /chief/human-messages` 201, row `1 style_prompt`; turn 2
  (`--resume <uuid>`, "use CSV ...") -> 201, row `2 human`, and the model, asked for the number in
  Pathly's note, answered `2`, so the hook's stdout line reaches the chief's context.
- Mutation check: 25 one-line breakages of `human.py`, `chief_prompt.py` and `chief_routes.py` (secret
  check off or its guards removed, the compare, session check off or loosened, closed check,
  `relayed` dropped, size check, byte vs character count, blank check, the body check, a non-string
  `run_id`, the marker off or narrowed to the start of the prompt, the `kind` check, a wrong
  `session_id` sent, a narrowed `except`, the timeout, a secret not stripped, the host, and adding the
  route to `ROUTE_ACTIONS` as `post`) were each run against the two new test files with the final
  tests: 25 of 25 failed (scratchpad `b09/mutate09.py`, every file restored afterwards). Two survived
  the first version of the tests (a session with no stored secret hash, and an empty
  `cli_session_id`), and `test_a_session_without_a_secret_or_a_claude_session_records_nothing` was
  added for them.
- Test command: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x
  -p no:cacheprovider` -> `3067 passed, 2 skipped in 815.97s`, exit 0 (the skips are not in the new
  files; no Python file changed after it started). Lint command, run link by link: black, mypy (332
  files), `check_file_size.py` (1027 files, 18 known over 400, none new, none grown),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (1 kept, 0 broken), bandit,
  `check_adapters.py`, `check_entry_points.py` all exit 0. Smoke exit 0. `python -m build --wheel`
  exit 0 and the wheel holds `pathly_hooks/chief_prompt.py` and `blueprints/chief/human.py`.

**Decisions**

- The marker is looked for anywhere in the prompt, not only at its start: a peer message that was
  queued with other text might arrive joined, and the wrong direction (a worker's words citable as
  the human's) is the one that matters. The cost is a typed prompt that quotes the tag becoming
  uncitable; the human retypes it.
- Blank `text` (spaces only) is a 400 as well as empty: the first stored message is the one that
  becomes `style_prompt`, so a blank first submission must not use that slot up.
- The hook prints nothing for a `relayed` reply (the spec prints the line "for a `human` message"):
  telling the chief to cite a message it can never cite would only produce a refused answer.
- The hook skips the post when the prompt or `session_id` is not a non-empty string (the server would
  answer 403 or 400 anyway), and reads stdin as bytes decoded as UTF-8 (a Windows locale would
  otherwise mangle a non-ASCII prompt).
- The text limit is a local `MAX_TEXT_BYTES = 64 * 1024` in `human.py`, not `chief_session.MAX_PROMPT_BYTES`,
  so the two limits can change apart.
- `relayed` is read with `bool(...)`: any truthy value, even the string "false", counts as relayed,
  the safe direction.

**Shortcuts taken**

- None in the code. The interactive-tab measurement used a pty and a sender addressed by its
  `uds:` path, because an interactive session wrote no `~/.claude/sessions/<pid>.json` entry (so
  `ListAgents` by name did not find it); a real person's second terminal was not used. The
  pasted-prompt path (the docs say pasted text arrives expanded, between `<pasted_content id=...>`
  lines in some sessions) was not measured.

**For later tickets**

- Ticket 10: a `human` message's `text` is exactly the hook's `prompt`. The docs say pasted text can
  arrive with `<pasted_content id="...">` marker lines around it; if ticket 10 relays the cited text
  verbatim to an agent those lines would go with it. Not measured here (needs a bracketed paste into
  an interactive tab). The style prompt is the first stored message (`style_prompt`, never citable).
- Ticket 10 (and the acceptance, 13): there are now two reasons a message is not `human`: it is the
  first of the session, or it arrived wrapped by another claude session. A codex chief has no hook and
  no `cli_session_id`, so `POST /chief/human-messages` can record nothing for it.
- Round two / ticket 06's settings: the docs name `crossSessionInbound: "refuse"` as the setting that
  turns inbound cross-session messages off; ticket 06's `claude_settings` does not set it. It is not
  needed while the chief runs `--restricted` (which binds no inbox on 2.1.304), but it is the line to add
  if the chief ever starts without `--restricted` (for example with `--setting-sources`). Not tried.
- `spec.md` rows 236-237 and the Risks entry say a message from another session "stays an open
  question if the hook cannot tell it apart"; they are records and were not edited. map.md's
  Open-questions bullet has the measured answer.
- A new chief route that a chief token must NOT reach needs nothing in the gate tables (unlisted =
  refused); only a route a chief may call needs `ROUTE_ACTIONS` and `ROUTE_FIELDS` entries.

**Minors noticed, not fixed**

- `docs/ARCHITECTURE.md` line 134 lists the hook scripts as `classify_feedback.py` and
  `inject_feedback_ttl.py` only (it also leaves out `stop_telemetry.py`); `docs/PATHLY_ARCHITECTURE.md`
  has the same generic wording. Outside this ticket and not a chief matter.
- `pathly_hooks/__init__.py` imports its two older hooks eagerly (with a `# noqa`), so
  `python -m pathly_hooks.chief_prompt` also imports them (about 0.1 s in all); harmless, left alone.
- The 2 skipped tests in the Test command are older tests; the file `tests/comms_board/test_chief_human_messages.py`
  was edited after the test-only commit (one added test), which is why the final diff touches it.
