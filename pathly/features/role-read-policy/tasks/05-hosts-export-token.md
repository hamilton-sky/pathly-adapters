# Put the run token into the spawned agent's environment in both spawn hosts

Type: task
Status: resolved
Blocked by: 04
Test first: yes

Both spawn hosts must set `PATHLY_RUN_TOKEN` in the child env from the payload's `run_token`
(SPEC.md § C4). The supervisor cannot tell them apart, so both get the same behaviour.

- **pty-host** (`src/pathly_orchestrator/pty_host/host.py`): `_child_env(cwd)` gains the token
  from the event; set `PATHLY_RUN_TOKEN` only when the payload carries one. Leave the existing
  `PATHLY_PROJECT_ROOT` and `PATHLY_GATE_BILLED` entries as they are.
- **Studio**: `renderer/src/components/TerminalSpawnListener.tsx` passes `data.run_token` to the
  `terminal:register-runner` IPC (preload bridge `studio/src/main/preload/index.ts` and its type
  declaration gain the extra optional argument). In `studio/src/main/ipc/terminal.ts`,
  `runnerTabMeta` keeps it, and the env for a runner tab includes `PATHLY_RUN_TOKEN`.
  `terminal.ts` is 391 lines: move the env assembly into a new
  `studio/src/main/ipc/terminal/spawnEnv.ts` (`buildSpawnEnv(cwd, meta)`) and call it, so the file
  shrinks rather than grows.
- The token is never written to `process.env` of the Studio main process and never logged.

## Not in this ticket

- The UI token for Studio's own requests: a later plan (RRP-2b).
- Fragments sending the header: ticket 07.

## Done when

- `python -m pytest tests/runner_supervisor/test_pty_host.py -q` passes, including a new test that
  a `TERMINAL_SPAWN` with `run_token` gives a child env with `PATHLY_RUN_TOKEN` equal to it, and
  one without gives no such key.
- `cd studio && npx vitest run src/main/ipc/terminal/spawnEnv.test.ts` passes: a runner tab with a
  token gets `PATHLY_RUN_TOKEN`, a non-runner tab does not, and `PATHLY_GATE_BILLED` behaves as
  before.
- `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json` and
  `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exit 0.
- `studio/src/main/ipc/terminal.ts` is shorter than 391 lines.

```check
$ python -m pytest tests/runner_supervisor/test_pty_host.py -q -p no:cacheprovider
exit 0
prints passed
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
exit 0
$ python -c "print('terminal.ts shorter:', sum(1 for _ in open('studio/src/main/ipc/terminal.ts',encoding='utf-8')) < 391)"
prints terminal.ts shorter: True
```

## Reference

- SPEC.md § C4
- `src/pathly_orchestrator/pty_host/host.py` (`_child_env`, the spawn handler)
- `studio/src/main/ipc/terminal.ts` (`terminal:spawn`, `terminal:register-runner`, env block),
  `studio/src/main/ipc/terminal/` (existing split-out modules), `studio/CLAUDE.md` (typecheck
  commands, IPC pattern)
- Ticket 04's Answer

## Answer

**Built**: `src/pathly_orchestrator/pty_host/host.py` (`_child_env(cwd, run_token=None)`; `_start` passes `event.get("run_token")`), new `studio/src/main/ipc/terminal/spawnEnv.ts` (`buildSpawnEnv(cwd, meta)`), `studio/src/main/ipc/terminal.ts` (env block replaced by the call; `register-runner` takes a 6th `runToken` arg; 391 -> 376 lines), `studio/src/main/ipc/terminal/ptyRegistry.ts` (`run_token?` on the `runnerTabMeta` value type), `studio/src/main/preload/index.ts` + `studio/src/renderer/src/types/global.d.ts` (optional `runToken` arg), `studio/src/renderer/src/components/TerminalSpawnListener.tsx` (passes `data.run_token`), tests (`tests/runner_supervisor/test_pty_host.py`, `studio/src/main/ipc/terminal/spawnEnv.test.ts`, committed first and failing), living docs (`studio/CLAUDE.md` module table, `src/pathly_orchestrator/CLAUDE.md` pty_host child-env paragraph), regenerated `tests/runner_supervisor/INDEX.md`.

**Proof**:
- `python -m pytest tests/runner_supervisor/test_pty_host.py -q -p no:cacheprovider` -> 21 passed (new: token in payload gives child `PATHLY_RUN_TOKEN` equal to it; payload with none / `None` / `""` gives no such key). Before the change the test commit failed with `KeyError: 'PATHLY_RUN_TOKEN'`.
- `cd studio && npx vitest run src/main/ipc/terminal/spawnEnv.test.ts` -> 5 passed (runner tab with token gets it; runner tab without token or with `""` does not; non-runner tab has neither `PATHLY_RUN_TOKEN` nor `PATHLY_GATE_BILLED`; runner tab keeps `PATHLY_GATE_BILLED=1`, `PATHLY_PROJECT_ROOT`, enriched `PATH`; `process.env.PATHLY_RUN_TOKEN` stays undefined). Before the change it failed on the missing module. `npx vitest run src/main` -> 33 passed.
- `tsc --noEmit -p studio/tsconfig.node.json` exit 0; `-p studio/tsconfig.web.json` exit 0.
- terminal.ts line check prints `terminal.ts shorter: True` (376 lines).
- commands.md: Test -> 916 passed, 2 skipped; Lint (black, check_file_size, check_no_mirror_reads, gen_test_index --check, lint-imports) all pass; Build and Smoke exit 0; `mypy src/ --ignore-missing-imports --no-strict-optional` -> no issues in 271 files; `bandit -r src/ -ll -x src/pathly_data/` reports no findings.

**Decisions**:
- The token is exported exactly as received. Only a non-empty string sets the key; `None`, `""` and non-strings set nothing. No role handling.
- Both hosts also strip a `PATHLY_RUN_TOKEN` inherited from their own environment (the pty-host process, Studio main) before adding the payload's, so an unrelated token can never reach a child that has none of its own. The ticket did not ask for this; it is two lines and stops a stale token being read as the run's.
- `buildSpawnEnv(cwd, meta)` takes a structural `{ run_token?: string }` (or `undefined` for a non-runner tab) rather than importing the registry type, so it imports only `./shells`; the test mocks `./shells` (which imports `electron`).
- Transient retries re-enter `handleSpawn`, which reads `runnerTabMeta` again, so a retried attempt keeps the same token.

**Shortcuts taken**: none.

**For later tickets**: the child process now has `PATHLY_RUN_TOKEN` set when the server minted a token; ticket 07 (fragments sending the header) can read it from the env. `run_token` can be absent (best-effort mint), so fragments must tolerate the var being unset. Studio's interactive (non-runner) tabs never get a token, by design (the UI token is RRP-2b).
