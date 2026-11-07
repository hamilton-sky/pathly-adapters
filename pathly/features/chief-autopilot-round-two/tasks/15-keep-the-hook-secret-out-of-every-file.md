# Keep the chief's hook secret out of every file: the server's claim route and the hook

Type: task
Status: claimed
Blocked by: 13
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/supervisor/chief_session.py, src/pathly_orchestrator/supervisor/chief_secret_claim.py (new), src/pathly_orchestrator/runner/chief_argv.py, src/pathly_hooks/chief_prompt.py, src/pathly_orchestrator/http_server/blueprints/chief/hook_secret.py (new), src/pathly_orchestrator/http_server/blueprints/chief/__init__.py, src/pathly_orchestrator/http_server/blueprints/chief/human.py, src/pathly_orchestrator/http_server/chief_secret_text.py, tests/runner_supervisor/test_chief_hook_secret_claim.py (new), tests/runner_supervisor/test_chief_session.py, tests/runner_supervisor/test_chief_settings_env.py, tests/runner_supervisor/test_chief_secret_reach.py, tests/comms_board/chief_acceptance_support.py, tests/comms_board/chief_human_support.py, tests/comms_board/test_chief_hook_tags.py, tests/comms_board/test_chief_prompt_hook.py, tests/comms_board/test_chief_human_messages.py, tests/comms_board/test_autopilot_round_one_acceptance.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md, tests/comms_board/INDEX.md

The brief's last In scope item (round one map, "Round two", last bullet): headless agents run with
`--dangerously-skip-permissions` and can read `~/.pathly/chief/<id>/hook_secret` (0600, written by
`chief_session._write_session_folder`), and with it and the chief's `--session-id` (in its argv)
post a `human` row. Full secrecy from same-user processes is impossible without OS isolation
(ticket 13); this ticket builds the server half of the measurable mitigation ticket 13 settled
(question 2 = A: a second claim closes the chief). Ticket 18 builds the Studio and pty-host half.

1. `chief_session._write_session_folder` writes no `hook_secret` file. For a claude chief the
   server generates the secret, stores only its sha256 (`hook_secret_hash`, as today) and keeps
   the plaintext in memory in new `src/pathly_orchestrator/supervisor/chief_secret_claim.py`
   (new): `offer(run_id, secret)`, `claim(run_id) -> str | None` (returns it once and forgets it;
   a second call returns None and calls `close_chief(run_id, "hook secret claimed twice")`),
   `forget(run_id)`, called from `close_chief`. A codex chief gets no secret and no hash (it has no
   hook); `chief_secret_text.secret_refusal` already skips a session with no hash.
2. New `POST /chief/hook-secret` `{run_id}` in
   `src/pathly_orchestrator/http_server/blueprints/chief/hook_secret.py` (new, registered through
   `blueprints/chief/__init__.all_blueprints`): 200 `{"hook_secret": ...}` once; 409 for a second
   claim (and the session is closed); 404 for an unknown or closed session; 403 for any caller that
   sends a run token (an agent's `pathly api` sends its own), so only a tokenless caller, Studio's
   main process, can claim. The route is not in `chief_routes.ROUTE_ACTIONS`, so the chief gate
   refuses it to a chief.
3. The hook settings (`runner/chief_argv.claude_settings`, via `chief_session._hook_command`) lose
   `--secret-file`; `src/pathly_hooks/chief_prompt.py` reads the secret from its environment,
   `PATHLY_CHIEF_HOOK_SECRET` (a command hook inherits claude's environment; docs:
   https://code.claude.com/docs/en/hooks), and still exits 0 when it is missing. The settings also
   deny `Bash(env*)`, `Bash(printenv*)` and `Read(/proc/**)` (and `Grep`/`Glob` on it), so the
   chief cannot print its own environment through its tools; the chief gate's body scan stays as
   defence in depth.

Docs: `src/pathly_orchestrator/CLAUDE.md` ("Human messages", "Chief gate") says where the secret
lives now and says plainly what stays true: while the chief runs, a same-user process can read its
environment (Linux `/proc/<pid>/environ`; macOS and Windows have their own same-user reads); a
codex chief has no secret to lose, but its read-only sandbox reads the whole file system, including
headless agents' live `PATHLY_RUN_TOKEN`s, so Pathly cannot promise it stays inside its project.
The tests that read the secret from the file (round one's acceptance and chief tests) get it
through `chief_secret_claim` or the new route instead; none is deleted.

Until ticket 18 lands, a real claude chief opened from Studio gets no secret in its environment,
so its hook records nothing (exit 0): citations are lost, nothing is forged. The tests drive the
hook with the variable set.

## Not in this ticket

- Studio claiming the secret and putting it in the chief's environment, the pty host stripping
  it, the launcher's text: ticket 18.
- OS isolation of headless agents (another uid, a sandbox): a later round (ticket 13).
- The trust screen on the chief's tab: ticket 14.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_hook_secret_claim.py -q -p no:cacheprovider`
  passes and covers: after `open_chief` no file under the session folder holds the secret
  (`db/secret_scan.contains_secret_hash` over every file) and the `TERMINAL_SPAWN` payload does not
  hold it; the first `POST /chief/hook-secret` is 200 with a secret whose sha256 is the stored
  hash; a second is 409 and the session is closed; a run-token caller is 403; a closed or unknown
  session is 404; a codex chief has no hash and its claim is 404; the settings deny `Bash(env*)`,
  `Bash(printenv*)` and `Read(/proc/**)`; the hook with `PATHLY_CHIEF_HOOK_SECRET` set records the
  prompt and with it unset records nothing and exits 0.
- All existing chief tests and round one's acceptance test still pass, and `tests/consistency`
  (`test_chief_tests_use_the_guard.py` covers the new chief test) passes.

```check
$ python -m pytest tests/runner_supervisor/test_chief_hook_secret_claim.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board tests/runner_supervisor tests/http_api -q -p no:cacheprovider -k chief
exit 0
$ python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py tests/consistency -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("The hook secret")
- `src/pathly_orchestrator/http_server/blueprints/chief/human.py` (module docstring: the exposure today)
- `tests/runner_supervisor/test_chief_secret_reach.py`

## Answer
