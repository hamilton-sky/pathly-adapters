# Hand the hook secret to the chief's claude in Studio, strip it everywhere else, and say so in the launcher

Type: task
Status: open
Blocked by: 13, 15
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/pty_host/host.py, tests/runner_supervisor/test_pty_host_strips_chief_secret.py (new), studio/src/main/ipc/terminal.ts, studio/src/main/ipc/terminal/chiefSecret.ts (new), studio/src/main/ipc/terminal/chiefSecret.test.ts (new), studio/src/main/ipc/terminal/spawnEnv.ts, studio/src/main/ipc/terminal/spawnEnv.test.ts, studio/src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.tsx, studio/src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx, studio/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

Split from ticket 15, which made the server keep the chief's hook secret in memory and offer it
once at `POST /chief/hook-secret`. This ticket makes Studio's main process the one claimer, keeps
the secret out of every other child, and tells the person what stays true (ticket 13's question 2
= A: a second claim closes the chief, so a Studio claim that loses the race is refused).

1. `pathly-pty-host` (`pty_host/host.py::_child_env`) removes `PATHLY_CHIEF_HOOK_SECRET` from
   every child's environment (it refuses interactive spawns, so it never claims one).
2. New `studio/src/main/ipc/terminal/chiefSecret.ts` (new): `claimChiefHookSecret(runId)` posts to
   `${getApiBase()}/chief/hook-secret` and returns the secret or null (non-200, network error).
   In `terminal.ts` `handleSpawn` (search `buildSpawnEnv(`), for an interactive runner tab whose
   `run_id` matches `^chief-[0-9a-f]{12}$` and whose argv starts with `claude`, claim before
   `buildSpawnEnv`; no secret means the spawn is refused with an error (the server's watcher closes
   the session as "never started"). `terminal.ts` is on the `Shared:` line, so this ticket is built alone.
3. `spawnEnv.buildSpawnEnv` deletes `PATHLY_CHIEF_HOOK_SECRET` for every child and sets it only
   from the claimed value; it is never written to Studio's own `process.env`, never logged, never
   sent to the renderer.
4. The chief launcher (`ChiefLauncher.tsx`) keeps its `CODEX_NOTE` and gains, for a claude chief,
   one plain line: while the chief runs, another program running as you can still read its
   environment, so keep untrusted programs off this account. Keep it one short sentence.

Note in `studio/CLAUDE.md` (the terminal spawn section) where the chief's secret comes from and
that no other child gets it.

## Not in this ticket

- The claim route, the in-memory store and the hook reading its environment: ticket 15.
- OS isolation of headless agents: a later round (ticket 13).

## Done when

- `python -m pytest tests/runner_supervisor/test_pty_host_strips_chief_secret.py -q -p no:cacheprovider`
  passes: the pty host's child env has no `PATHLY_CHIEF_HOOK_SECRET` even when the host's own has one.
- `npm --prefix studio run test -- src/main/ipc/terminal/spawnEnv.test.ts src/main/ipc/terminal/chiefSecret.test.ts`
  passes and covers: a non-chief child never gets `PATHLY_CHIEF_HOOK_SECRET`, even when Studio's
  own environment has one; a chief child gets exactly the claimed value; a claim that answers 409
  or fails returns null and the chief spawn is refused.
- `npm --prefix studio run test -- src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx`
  passes and covers: a claude chief's launcher shows the same-user line; a codex chief's shows
  `CODEX_NOTE`.
- The main-process typecheck, Studio's renderer typecheck and the Studio suite pass.

```check
$ python -m pytest tests/runner_supervisor/test_pty_host_strips_chief_secret.py -q -p no:cacheprovider
exit 0
prints passed
$ npm --prefix studio run test -- src/main/ipc/terminal/spawnEnv.test.ts src/main/ipc/terminal/chiefSecret.test.ts
exit 0
prints passed
$ npm --prefix studio run test -- src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx
exit 0
prints passed
$ node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ npm --prefix studio run typecheck
exit 0
$ npm --prefix studio run test
exit 0
```

## Reference

- spec.md § Decisions ("The hook secret")
- `studio/src/main/ipc/terminal/spawnEnv.test.ts` (how a main-process module is tested with vitest)
- `tests/runner_supervisor/test_chief_secret_reach.py`

## Answer
