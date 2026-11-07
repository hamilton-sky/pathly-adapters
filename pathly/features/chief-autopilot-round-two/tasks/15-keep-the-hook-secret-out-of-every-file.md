# Keep the chief's hook secret out of every file: the server's claim route and the hook

Type: task
Status: resolved
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

Work started at `5568542608836417d935e179962380cd5820898f` (HEAD when claimed; the build prompt
named `ea055fe`, which a later merge commit followed). Failing-test commit: `7a04baa`.

**Built**

- `src/pathly_orchestrator/supervisor/chief_secret_claim.py` (new): `offer`, `claim` (hands the
  secret on once; any later call returns None and calls `close_chief(run_id, "hook secret claimed
  twice")` without holding the lock), `forget`.
- `supervisor/chief_session.py`: `_write_session_folder` writes no `hook_secret` (claude:
  `settings.json` + `mcp.json`; codex: an empty folder); `open_chief` generates the secret for a
  claude chief only, stores its sha256 and `offer`s it under `_open_lock` right after the row is
  created; a codex chief gets `hook_secret_hash=None`; `_hook_command(run_id)` has no
  `--secret-file`; `close_chief` calls `forget` in its `finally`.
- `http_server/blueprints/chief/hook_secret.py` (new) `POST /chief/hook-secret`, registered in
  `blueprints/chief/__init__.all_blueprints`: 403 for a live run token (`session._refuse_agent`;
  a chief token is already refused by the chief gate), 400 for a non-object body, 404 for an
  unknown/closed session or one with no hash, 200 `{hook_secret}` with `Cache-Control: no-store`,
  409 for a later claim (session closed, `TERMINAL_KILL` sent to its tab via `session._kill_tab`).
  Not added to `chief_routes.ROUTE_ACTIONS`.
- `runner/chief_argv.py`: deny `Bash(env*)`, `Bash(printenv*)`, `Read(/proc/**)`,
  `Read(//proc/**)`, `Grep(//proc/**)`, `Glob(//proc/**)`; docstring.
- `src/pathly_hooks/chief_prompt.py`: no `--secret-file`; reads `PATHLY_CHIEF_HOOK_SECRET`
  (stripped; unset/blank records nothing, exit 0).
- Docstrings: `blueprints/chief/human.py`, `http_server/chief_secret_text.py`.
- Tests: new `tests/runner_supervisor/test_chief_hook_secret_claim.py` (17 tests); updated
  `test_chief_session.py` (DENY list, empty codex folder + no hash, hook argv, secret via
  `claim`, file modes), `test_chief_settings_env.py`, `test_chief_secret_reach.py` (+6 cases),
  `chief_human_support.py` (`open_session` claims; fixture `secret_file` -> `hook_secret_env`
  setting the variable; `argv_for()`), `test_chief_hook_tags.py`, `test_chief_prompt_hook.py`
  (subprocess hooks get the variable in their env; missing-secret case parametrized unset /
  empty / blank), `test_chief_human_messages.py`, `chief_acceptance_support.py` (`hook_secret`
  claims once through the route and caches per run id; `type_in_tab` uses it),
  `test_autopilot_round_one_acceptance.py`. No test deleted or skipped.
- Docs: `src/pathly_orchestrator/CLAUDE.md` (route table, deny paragraph, "Human messages" with
  "Where the secret lives" and "What stays true", "Chief gate" hook-secret bullet, citation
  paragraph, file tree for `chief_session.py`, `chief_secret_claim.py`, the chief blueprints);
  `tests/INDEX.md`, `tests/runner_supervisor/INDEX.md` regenerated.

**Proof**

- `python -m pytest tests/runner_supervisor/test_chief_hook_secret_claim.py -q -p no:cacheprovider`:
  `17 passed`. It covers: no file in the session folder holds the secret
  (`contains_secret_hash` over every file, and the claimed plaintext is in none), nor the
  `TERMINAL_SPAWN` payload; first claim 200 with sha256 == stored hash; second 409, session
  closed with reason `hook secret claimed twice`, third 404; run token (builder and chief) 403
  and the refusal spends nothing; unknown (5 ids) and closed 404; codex has no hash, empty
  folder, claim 404 and stays open; deny rules; hook with the variable records `style_prompt`
  then `human` and prints the cite line, unset or blank records nothing and exits 0. At
  `7a04baa` the same command failed at collection (`ImportError: cannot import name
  'chief_secret_claim'`).
- `python -m pytest tests/comms_board tests/runner_supervisor tests/http_api -q -p no:cacheprovider -k chief`:
  `2739 passed, 1877 deselected`, exit 0.
- `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py tests/consistency -q -p no:cacheprovider`:
  `97 passed`.
- Full suite `python -m pytest tests -q -p no:cacheprovider -x`: `6828 passed, 14 skipped`,
  exit 0. `black --check src/ tests/`, mypy, `check_file_size.py` (none new, none grown;
  `chief_session.py` 355 lines), `check_no_mirror_reads.py`, `gen_test_index.py --check`,
  `lint-imports` (1 kept), bandit, `check_adapters.py`, `check_entry_points.py`: all exit 0.

**Decisions**

- `Read(/proc/**)` is kept because the ticket names it, but claude's permissions docs
  (https://code.claude.com/docs/en/permissions, fetched 2026-11-07) say a single leading slash
  anchors at the settings source and `//` is the filesystem root. So `Read/Grep/Glob(//proc/**)`
  are the rules that actually reach `/proc`; both forms are in the list.
- `claim` closes on any call that finds nothing to hand on (not only an exact "second"): the
  route 404s before claiming for unknown, closed and hashless sessions, so in practice that is
  the second claim; closing an unknown or closed session is a no-op.
- The 409 also sends `TERMINAL_KILL` to the tab (as `POST /chief/close` does), since a
  closed chief's tab would otherwise linger with a revoked token.
- The route reuses `session._refuse_agent` / `_kill_tab` by import rather than copying them
  (moving them to a `_helpers.py` would touch `session.py`, outside Touches).
- The offer happens inside `_open_lock` right after `create_session`, so the route never sees
  an open claude row without an offered secret.

**Shortcuts taken**

- Secrets live in the server process's memory only: a server restart loses them (startup
  cleanup closes those sessions anyway). Fine while one server process serves a machine.
- The acceptance helper caches a claimed secret per run id in a module dict; harmless because
  run ids are random.

**For later tickets**

- 18: claim with tokenless `POST /chief/hook-secret {run_id}` after the chief's
  `TERMINAL_SPAWN`, exactly once per chief (a second claim closes it and kills the tab), and set
  `PATHLY_CHIEF_HOOK_SECRET` in the chief claude's environment only. The spawn payload carries
  no secret and no hint to claim; Studio keys on the `chief:` topic / `chief-` run id.
- Root `CLAUDE.md`'s chief blueprint list (`chief/` row of the domain map) does not name
  `POST /chief/hook-secret`; it was outside this ticket's Touches.


**Rework, round 1** (work started at `6ec2edc`; docs and docstrings only, no behaviour change)

**Review fixes**

- 1 (major, docs): `src/pathly_orchestrator/CLAUDE.md` "Where the secret lives" no longer says
  "its hook records nothing: citations are lost, nothing is forged". It now says that until
  ticket 18 nothing claims the secret, so any tokenless same-user process can claim it, read the
  `--session-id` from the chief's argv and post `human` rows unnoticed (no second claim ever
  comes; exposure about that of the old 0600 file), and that the second-claim detection exists
  only once Studio makes the expected claim. The docstrings that implied the claim-once rule
  protects the secret today now say the same: `blueprints/chief/human.py`,
  `blueprints/chief/hook_secret.py`, `supervisor/chief_secret_claim.py` (module docstring).
  `http_server/chief_secret_text.py` also claimed "the guarantee ... is that the chief cannot read
  its environment"; that sentence is gone.
- 2 (minor): the deny-list comment in `runner/chief_argv.py`, the `pathly api` deny paragraph
  and the "Hook secret in a body" bullet of the Chief gate docs, `human.py` and
  `chief_secret_text.py` now say the deny rules do not stop the shell expanding
  `$PATHLY_CHIEF_HOOK_SECRET` (or a slice) inside an allowed `pathly api` body, and a slice passes
  the body scan. No doc claims the chief cannot print its environment. No new deny rule (not
  measured against claude's matcher; outside what the ticket asks).
- 3 (minor): `chief_secret_claim.claim`'s docstring and the CLAUDE.md section note that a claim
  with nothing offered (before `offer`, or after a server restart) closes an open chief.
- 4 (minor): `Read(/proc/**)` left as is, as instructed (the ticket names it; harmless).

**Proof (rework)**, re-run on the reworked tree:
- `python -m pytest tests/runner_supervisor/test_chief_hook_secret_claim.py -q -p no:cacheprovider`:
  `17 passed`.
- `python -m pytest tests/comms_board tests/runner_supervisor tests/http_api -q -p no:cacheprovider -k chief`:
  `2739 passed, 1877 deselected`, exit 0.
- `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py tests/consistency -q -p no:cacheprovider`:
  `97 passed`.
- Full `python -m pytest tests -q -p no:cacheprovider`: `6828 passed, 14 skipped`, exit 0.
- `black --check src/ tests/` (756 unchanged), `lint-imports` (1 kept, 0 broken),
  `gen_test_index.py --check` (up to date), `check_file_size.py` (none new, none grown): exit 0.

## Review findings (round 1, quality review)

QUALITY
Scope: reviewed ea055fe..926ab0b (END is HEAD; no later commits were left out). I read the ticket at ea055fe, so its Answer never reached me. I re-ran all three Done when checks: 17 passed; 2739 passed (-k chief, 1877 deselected); 97 passed (round one acceptance + tests/consistency). git status was clean afterwards.

Inputs I probed as a hostile caller:
- POST /chief/hook-secret: run_id (missing, non-string, unknown, closed, codex), the body shape, X-Pathly-Run-Token (builder, chief, revoked: run_token_guard refuses a revoked one before the route), two concurrent claims (pop under the lock, so exactly one 200), claim racing close_chief (404, or 409 with a harmless second close), a browser Origin (the api-secret CSRF check runs first; api_secret is always set).
- PATHLY_CHIEF_HOOK_SECRET in the hook (unset or blank: exit 0, nothing recorded).
- The chief's own tools: Bash is allowed only for `pathly *` with dontAsk. `pathly api` refuses to run without PATHLY_RUN_TOKEN, so the chief cannot make a tokenless claim or post. The route refuses a chief token (403 from _refuse_agent, and the chief gate).
- The secret's homes: no file, no TERMINAL_SPAWN payload, no log line (only the path and the status are logged), Cache-Control: no-store, forgotten in close_chief's finally, lost on restart.

1. major src/pathly_orchestrator/CLAUDE.md ("Where the secret lives"): the doc says that until ticket 18 lands, "its hook records nothing: citations are lost, nothing is forged". That is not true of the code in this commit. Nothing claims the secret before ticket 18, so a headless agent (running with --dangerously-skip-permissions) can `curl -X POST 127.0.0.1:8765/chief/hook-secret -d '{"run_id":...}'` with no token header, which counts as anonymous. It gets 200 and the secret. It reads the chief's --session-id from the process list (`ps`) and posts `human` rows to /chief/human-messages. No second claim ever happens, so the chief is never closed and the theft goes unnoticed. The exposure is about the same as the 0600 file it replaces, so this is not a regression. But this living doc is loaded into agents' context and states a security property that does not hold. Change: say plainly that until ticket 18, any tokenless same-user process can claim the secret and nothing detects it. The detection (a second claim closes the chief) only exists once Studio makes the expected claim. The same wording in the ticket text should not be copied into later docs. Also check human.py's module docstring, which implies the claim-once property protects the secret today.
2. minor src/pathly_orchestrator/runner/chief_argv.py: denying `Bash(env*)` and `Bash(printenv*)` does not stop shell expansion of `$PATHLY_CHIEF_HOOK_SECRET` (or `${PATHLY_CHIEF_HOOK_SECRET:0:20}`) inside an allowed `pathly api ...` body. A partial or split secret gets past the gate's body scan, so a chief steered by prompt injection could leak it to the board in pieces. I did not measure it against claude's matcher. Its value to an attacker is low, because any same-user process can read /proc/<pid>/environ anyway. Change: note this in the deny-list comment and the Chief gate docs, or deny `$PATHLY_CHIEF_HOOK_SECRET` patterns as well. Do not claim the chief "cannot print its environment".
3. minor src/pathly_orchestrator/supervisor/chief_secret_claim.py: when claim() finds no offered secret it closes the chief, whatever the reason. A claim that lands in the gap between create_session and offer(), or any claim after a restart, closes a healthy chief. Any tokenless caller can already close a chief on purpose by claiming twice, which is the accepted q2=A trade-off. Change: none needed; a one-line note in the docstring would help ticket 18.
4. minor src/pathly_orchestrator/runner/chief_argv.py: `Read(/proc/**)` is kept although, by its own comment, it does not reach /proc. It exists only because the ticket named it. Harmless.

REVIEW: FAIL
