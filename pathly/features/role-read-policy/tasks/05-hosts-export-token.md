# Put the run token into the spawned agent's environment in both spawn hosts

Type: task
Status: open
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
