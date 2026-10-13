# Open and close a chief session in the supervisor

Type: task
Status: open
Blocked by: 04, 05
Test first: yes

The chief is a long-lived interactive spawn, so it cannot go through `_run_stage_via_terminal`
(it blocks its caller and times out after 30 minutes). Build its own open path from the same
pieces.

Add `src/pathly_orchestrator/runner/chief_argv.py` (pure, no I/O):

- `chief_argv(engine, model, settings_path) -> list[str]`: claude → `["claude"]`, then
  `["--model", model]` only when a model is given, then `["--settings", settings_path]`; codex →
  `["codex", "--sandbox", "read-only", "--ask-for-approval", "on-request"]` plus the optional
  model pair (read-only: codex cannot edit files and asks before every command). Never a
  permission-bypass flag, never the prompt, never the token. Any other engine raises
  `ValueError`.
- `claude_settings(hook_command) -> dict`: `permissions.allow = ["Bash(pathly *)"]`,
  `permissions.deny = ["Edit", "Write", "NotebookEdit", "Agent", "CronCreate", "Workflow",
  "Read(~/.pathly/**)"]`, and one `UserPromptSubmit` command hook running `hook_command`.

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
  <port>` (port from `config.Settings.from_env().port`, paths quoted for the shell); a
  `chief_sessions` row with the secret's sha256; `create_run(run_id)`; then
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
  token appears in neither `prompt` nor `argv`; claude argv has `--settings` and no
  `--dangerously-skip-permissions`; codex argv has `--sandbox read-only`; the settings file holds
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
- map.md § Decisions so far (docs: cli-reference, permissions, tools-reference)

## Answer
