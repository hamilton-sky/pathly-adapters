# Open and close a chief session in the supervisor

Type: task
Status: resolved
Blocked by: 04, 05
Test first: yes

The chief is a long-lived interactive spawn, so it cannot go through `_run_stage_via_terminal`
(it blocks its caller and times out after 30 minutes). Build its own open path from the same
pieces.

Add `src/pathly_orchestrator/runner/chief_argv.py` (pure, no I/O):

- `chief_argv(engine, model, settings_path, mcp_path, session_id) -> list[str]`: claude →
  `["claude", "--restricted", "--tools", "Bash,Read,Glob,Grep", "--settings", settings_path,
  "--mcp-config", mcp_path, "--strict-mcp-config", "--session-id", session_id]`, then
  `["--model", model]` only when a model is given. `mcp_path` holds `{"mcpServers": {}}`, so the
  chief gets none of the user's or project's MCP servers (Serena's edit tools, the `pathly-fsm`
  MCP). codex → `["codex", "--sandbox", "read-only", "--ask-for-approval", "on-request"]` plus the
  optional model pair (read-only: codex cannot edit files and asks before every command;
  `session_id` is ignored). Never a permission-bypass flag, never the prompt, never the token.
  Any other engine raises `ValueError`.
- Why `--restricted` and `--tools`: permission rules from every settings file claude loads
  merge, so a user or project allow rule such as `Bash(python3 *)` or `WebFetch` would otherwise
  let the chief reach the server without its token, and anonymous loopback callers are
  unrestricted until RRP-2b. On claude 2.1.292, `claude --help` says `--restricted` ignores user,
  project and local settings files while managed settings and `--settings` still apply, removes
  the tools that run commands and `WebFetch` unless `--tools` names them, confines the file tools
  to the working directories and refuses `bypassPermissions`; `--tools` sets the built-in tool
  list. So the chief has Bash (for `pathly`), Read, Glob and Grep, and nothing else. Check on the
  installed claude that the `UserPromptSubmit` hook from `--settings` still fires under
  `--restricted`. If it does not, drop `--restricted` and pass `--setting-sources` with an empty
  value instead (it also skips the user, project and local files) and keep `--tools`; the deny
  list below already covers `WebFetch` and `WebSearch` for that case. Write what you found in
  `learnings.md`.
- `claude_settings(hook_command) -> dict`: `permissions.allow = ["Bash(pathly *)"]`,
  `permissions.deny = ["Edit", "Write", "NotebookEdit", "Agent", "CronCreate", "Workflow",
  "WebFetch", "WebSearch", "Read(~/.pathly/**)", "Bash(curl *)", "Bash(wget *)"]`, and one
  `UserPromptSubmit` command hook running `hook_command`. Most of these tools are already absent
  under `--tools`; the denies stay so the rules still hold if a claude version reads `--tools`
  differently. Every Bash command other than `pathly …` asks the human.

Add `src/pathly_orchestrator/supervisor/chief_session.py`:

- `open_chief(*, project_root, engine, preset, prompt, model="", broadcast_fn,
  start_timeout=30.0) -> dict`. Validate: engine in `("claude", "codex")`, `project_root` an
  existing directory, `prompt` a non-empty string of at most 64 KiB (`ValueError` otherwise). If
  `queries.chief.open_session_for_project` finds one, raise `ChiefAlreadyOpen(run_id, tab_id)`.
  Then: tier from `chief_tiers.resolve_preset_tier(preset, project_root)`; `run_id = tab_id =
  "chief-" + 12 hex chars`; a token from `mint_run_token(conn, run_id, "chief", None,
  project_root, "project", scope)` with `scope` the project board scope
  (`fsm_compose.resolve_board_scope("project", project_root, "")`); a session folder
  `_chief_root() / run_id` (`_chief_root()` returns `~/.pathly/chief`, a function so tests can
  point it elsewhere) holding `hook_secret` (a `secrets.token_urlsafe(32)`) and, for claude,
  `settings.json` from `claude_settings`, both written mode 0600, with the hook command
  `<sys.executable> -m pathly_hooks.chief_prompt --run-id <run_id> --secret-file <path> --port
  <port>` (port from `config.Settings.from_env().port`, paths quoted for the shell),
  and for claude `mcp.json` holding `{"mcpServers": {}}`; for claude a `cli_session_id =
  str(uuid.uuid4())`, passed to `chief_argv` (codex: None); a `chief_sessions` row with the
  secret's sha256 and the `cli_session_id`; `create_run(run_id)`; then
  `broadcast_fn(topic, payload)` with the `TERMINAL_SPAWN` payload in spec.md § Interfaces
  (`topic = "chief:" + run_id`, `prompt` = `chief_tiers.strip_front_matter(prompt)`,
  `interactive: True`, `submit: False`, `label: "Chief · " + tier title`). Start a daemon watcher
  thread and return `{run_id, tab_id, tier, engine}`.
- The watcher: `get_run(run_id).wait_started(start_timeout)`; if that fails, close with reason
  `never started`; otherwise `wait_pty_result(None)` and close with reason `tab closed`. Studio's
  result post and `pathly-pty-host`'s refusal of interactive spawns both arrive through the
  existing `/runner/terminal/result` handler, which finds the run by `get_run`.
- `close_chief(run_id, reason) -> bool`: `queries.chief.close_session` (which revokes the
  token), remove the session folder, `drop_run(run_id)`. Safe to call twice.

Tests must not patch the global `time.sleep` (the WAL checkpoint daemon in `db/connection.py`
shares it); wait for the watcher with a bounded poll on `time.monotonic()` instead. Check file
modes only when `os.name == "posix"`, inside the test, not with a skip marker.

## Not in this ticket

- The HTTP routes and the startup close: ticket 07.
- The hook module that receives the prompts: ticket 09.
- Paste without Enter on the Studio side: round two (`map.md` § Round two).

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_session.py -q -p no:cacheprovider` passes
  and covers: with a fake broadcaster, `open_chief` emits one `TERMINAL_SPAWN` with
  `interactive` true, `submit` false, the front matter stripped from `prompt`, and a `run_token`
  that `resolve_run_token` maps to role `chief`, board `project` and the session's run id; the
  token appears in neither `prompt` nor `argv`; claude argv has `--settings`,
  `--strict-mcp-config`, an `--mcp-config` file with no servers, `--tools` with exactly
  `Bash,Read,Glob,Grep`, either `--restricted` or `--setting-sources` with an empty value, and
  `--session-id` with the UUID stored as the session's `cli_session_id`, and no
  `--dangerously-skip-permissions`; codex argv has no `--session-id` and its session's
  `cli_session_id` is None; the settings allow list is exactly `["Bash(pathly *)"]` and
  the deny list has `Bash(curl *)`, `Bash(wget *)` and `WebFetch`; codex argv has `--sandbox read-only`; the settings file holds
  the hook command with the run id and the deny list; a second open raises `ChiefAlreadyOpen`;
  `copilot` raises `ValueError`; after `mark_started()` and `mark_pty_result(...)` the token is
  revoked, the folder is gone and `get_run(run_id)` is None; with `start_timeout` near zero and no start, the session closes with
  reason `never started`.
- `lint-imports` exits 0.

```check
$ python -m pytest tests/runner_supervisor/test_chief_session.py -q -p no:cacheprovider
exit 0
prints passed
$ lint-imports
exit 0
```

## Reference

- spec.md § Design, § Decisions ("The chief's spawn", "Engines", "The chief's claude
  permissions"), § Interfaces
- `src/pathly_orchestrator/supervisor/registry.py` (`create_run`, `get_run`, `drop_run`,
  `TerminalRun.wait_started`, `wait_pty_result`)
- `src/pathly_orchestrator/supervisor/terminal.py::_run_stage_via_terminal` (payload shape to
  mirror; read-only)
- `src/pathly_orchestrator/runner/argv.py::resolve_interactive_argv` (always adds `--model`,
  which is why the chief has its own builder)
- `tests/comms_board/test_rrp_acceptance.py` (fake broadcaster that marks the run started and
  finished)
- map.md § Decisions so far (docs: cli-reference, permissions, tools-reference; claude 2.1.292
  `--help` for `--restricted`, `--tools`, `--setting-sources` and `--session-id`). Check
  `--mcp-config`, `--strict-mcp-config`, `--restricted` (with the `--settings` hook) and
  `--session-id` against `claude --help` and one real start on the installed claude before
  writing the argv, and note what you find in `learnings.md`. If the installed claude lacks
  `--restricted` and `--setting-sources`, stop and ask: without them the chief inherits the
  user's allow rules

## Answer

**Built**

- `src/pathly_orchestrator/runner/chief_argv.py` (new, pure): `chief_argv(engine, model,
  settings_path, mcp_path, session_id)` and `claude_settings(hook_command)`. claude gets
  `--restricted --tools Bash,Read,Glob,Grep --settings … --mcp-config … --strict-mcp-config
  --session-id …` and `--model` only when given; codex gets `--sandbox read-only
  --ask-for-approval on-request` and the optional model pair; any other engine is a `ValueError`.
- `src/pathly_orchestrator/supervisor/chief_session.py` (new): `ChiefAlreadyOpen(run_id, tab_id)`,
  `open_chief(...)`, `close_chief(run_id, reason)`, the watcher thread (`chief-watch-<run_id>`) and
  `_chief_root()`.
- `tests/runner_supervisor/test_chief_session.py` (new, 44 tests incl. parametrized; committed alone
  first as `9131286` `test(chief-agent): 06 failing test`; at that commit it failed at collection with
  `ModuleNotFoundError: No module named 'pathly_orchestrator.runner.chief_argv'`, the right reason).
  `tests/INDEX.md` and `tests/runner_supervisor/INDEX.md` regenerated.
- `src/pathly_orchestrator/CLAUDE.md`: one line each for `chief_argv.py` and `chief_session.py` in the
  package tree (the root `CLAUDE.md` documentation-sync rule; tickets 04 and 05 did the same).
- `learnings.md` (two lines) and `map.md` (one Decisions line).

**Proof** (each run fresh, after the last edit to code or tests)

- `python -m pytest tests/runner_supervisor/test_chief_session.py -q -p no:cacheprovider` -> `44
  passed in 8.75s`, exit 0. It covers every item of the Done when: one `TERMINAL_SPAWN` with
  `interactive` true, `submit` false, the front matter gone from `prompt`, topic `chief:<run_id>`,
  label `Chief · Operator`; `resolve_run_token` maps the payload token to role `chief`, board
  `project`, scope `resolve_board_scope("project", root, "")` and the session's run id; the token is
  in neither `prompt`, nor `argv`, nor any file of the session folder; claude argv has `--settings`
  (the folder's file), `--strict-mcp-config`, an `--mcp-config` file that parses to `{"mcpServers":
  {}}`, `--tools` exactly `Bash,Read,Glob,Grep`, `--restricted`, `--session-id` with a UUID equal to
  the session's `cli_session_id`, and no `--dangerously-skip-permissions`; codex argv has `--sandbox
  read-only`, no `--session-id`, `cli_session_id` None and a folder holding only `hook_secret`; the
  settings allow list is exactly `["Bash(pathly *)"]`, the deny list is the eleven entries (incl.
  `Bash(curl *)`, `Bash(wget *)`, `WebFetch`), and the hook command, split with `shlex.split` from a
  folder whose name has a space, is `[sys.executable, -m, pathly_hooks.chief_prompt, --run-id, <id>,
  --secret-file, <folder>/hook_secret, --port, 8123]`; a second open raises `ChiefAlreadyOpen` with
  the first run's ids and sends nothing; `copilot` is a `ValueError`; after `mark_started()` and
  `mark_pty_result(...)` the token is revoked (`resolve_run_token` None, `lookup_run_token` has
  `revoked_at`), the folder is gone, `get_run` is None and the session reads `tab closed`; with
  `start_timeout=0.05` and no start the session closes with reason `never started`. The mode check
  (0600 on `hook_secret`, `settings.json`, `mcp.json`) runs under `if os.name == "posix"` inside the
  test. No test patches `time.sleep`.
- Mutation checks (source edited, suite run, source restored): dropping `--strict-mcp-config`,
  `submit: True`, the token appended to `prompt`, skipping the folder removal, skipping the watcher
  release, skipping the already-open check and mode `0o644` each made a named test fail. I ran the
  file 25 times in a row after fixing a test-side race (below): 25 of 25 passed.
- `lint-imports` -> exit 0, `Orchestrator layer rule (db -> runner -> supervisor -> http_server) KEPT
  (3 ignored imports)`, `Contracts: 1 kept, 0 broken.`
- The rest of the Lint chain from `commands.md`, run piece by piece, all exit 0: `black --check src/
  tests/` (580 files unchanged), `mypy src/ ...` (`Success: no issues found in 319 source files`),
  `check_file_size.py` (`none new, none grown`; `chief_session.py` is under 400 lines),
  `check_no_mirror_reads.py`, `gen_test_index.py --check`, `bandit -q -r src/ -ll -x
  src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`. Smoke command exit 0; both new
  modules also import alone and in either order.
- Test command from `commands.md` (`tests/comms_board tests/db tests/runner_supervisor
  tests/http_api`) -> `1308 passed, 2 skipped in 264.79s`, exit 0 (the 2 skips are not mine).
- The real-claude check the Reference asks for, on the installed claude **2.1.302** (not 2.1.292), with
  `-p` on `--model haiku`: `--restricted --tools "Bash,Read,Glob,Grep" --settings <file with a
  UserPromptSubmit hook> --mcp-config <{"mcpServers": {}}> --strict-mcp-config --session-id <uuid>`.
  The hook fired, its stdin `session_id` was the `--session-id`, and the stream-json init event listed
  `tools` = Bash, Glob, Grep, Read and `mcp_servers` = []. See `learnings.md`.

**Decisions**

- `--restricted` stays, `--setting-sources` is not used: the `--settings` hook fires under
  `--restricted` on the installed claude. The check was run with `-p`; an interactive tab could not
  be started in this environment, so the interactive path is the same hook machinery but not observed.
- The folder and the session row are made before the token is minted, so a failure before the row
  exists leaves no token to revoke; a failure after (mint, `create_run`, the broadcast) runs
  `close_chief(run_id, "open failed")`, which revokes, removes the folder and drops the run. A
  `threading.Lock` makes the already-open check and `create_session` one step inside this process.
- `close_chief` also calls `mark_started()` and `mark_pty_result({"closed": reason})` on a run that is
  still registered before dropping it. Without that, a session closed by a route (ticket 07) leaves a
  watcher thread waiting for a result that can never come. Closing is not atomic: `closed_at` is set
  first, the folder is removed and the run dropped after (in a `finally`, so a DB error still removes
  the secret).
- `close_chief` returns False for an id that is not `chief-` plus 12 hex chars, before it touches any
  path, so a bad id cannot make `rmtree` reach outside `~/.pathly/chief`.
- Validation beyond the ticket's list, at a trust boundary: `preset` must be a string, `model` a string
  that does not start with `-` (it becomes an argv element), and the prompt must be non-empty after its
  front matter is stripped (a front-matter-only prompt would paste nothing). The 64 KiB limit is on the
  UTF-8 bytes of the prompt as given.
- `hook_secret_hash` is the sha256 hex digest of the secret's UTF-8 bytes, the same function
  `run_tokens` uses for tokens. `settings_dir` stores the session folder path.
- A codex session folder holds `hook_secret` only (no `settings.json`, no `mcp.json`), and the hook
  command, hence `Settings.from_env()`, is only built for claude.
- `project_root` is stored and compared as given, with no normalisation, as the token's `project_root`
  is too; the board scope is normalised by `resolve_board_scope`.
- The `run_token` is in the payload as the ticket and spec say; ticket 01 already strips it from every
  channel but `/events/spawn`.
- A test-side race found and fixed: the first version of the `never started` test read `get_run` as soon
  as `closed_at` appeared, but `drop_run` is the last step of the close. The test now waits for
  `get_run(run_id) is None` first. An autouse fixture also closes any chief a test leaves open, so no
  watcher outlives its test's patched home.

**Shortcuts taken**

none

**For later tickets**

- Ticket 07: map `ChiefAlreadyOpen` to 409 `{error, run_id, tab_id}` and `ValueError` to 400. Call
  `close_chief(run_id, ...)` from `/chief/close` and also send the host a `TERMINAL_KILL` for the tab:
  `close_chief` does not kill the process. `queries.chief.close_stale_sessions` revokes tokens but
  does not remove folders, so the startup cleanup must also clear `_chief_root()` (the folders hold the
  hook secrets). Normalise `project_root` the same way on open, close and session lookup, or a trailing
  slash escapes the one-chief-per-project check. `open_chief` pastes `strip_front_matter(prompt)` only;
  ticket 17's `chief-connect` fragment has to be appended by the caller or inside `open_chief` (the
  64 KiB limit is checked before any append). `Settings.from_env()` runs on each claude open: it can
  create the server secret file and exits on an invalid `PATHLY_FSM_HTTP_PORT`, which cannot happen in
  a running server.
- Ticket 09: the hook module is `pathly_hooks.chief_prompt` with `--run-id`, `--secret-file`, `--port`;
  the secret file holds the raw secret, the session row holds its sha256 hex (compare with
  `hmac.compare_digest`); `chief_sessions.cli_session_id` is what a hook post's `session_id` must equal.
- Ticket 08: the session's tier is `chief_sessions.tier` (what `resolve_preset_tier` returned); the
  token's `board` is `project` and its `scope` the normalised project root.
- With only `pathly-pty-host`, the refusal posts a result without a `started`, so the watcher closes the
  session after `start_timeout` (30 s) as `never started`, not at once. If that delay matters, the
  watcher can also wake on a result; the ticket asked for the plain two-step wait.
- Ticket 15 adds `chief_sessions.runs_started`; `open_chief` calls `create_session` without it.
