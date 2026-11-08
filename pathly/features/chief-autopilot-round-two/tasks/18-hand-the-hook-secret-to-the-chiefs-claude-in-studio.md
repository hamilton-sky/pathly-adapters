# Hand the hook secret to the chief's claude in Studio, strip it everywhere else, and say so in the launcher

Type: task
Status: resolved
Blocked by: 13, 15
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/pty_host/host.py, tests/runner_supervisor/test_pty_host_strips_chief_secret.py (new), studio/src/main/ipc/terminal.ts, studio/src/main/ipc/terminal/chiefSecret.ts (new), studio/src/main/ipc/terminal/chiefSecret.test.ts (new), studio/src/main/ipc/terminal/spawnEnv.ts, studio/src/main/ipc/terminal/spawnEnv.test.ts, studio/src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.tsx, studio/src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx, studio/CLAUDE.md, src/pathly_orchestrator/CLAUDE.md, CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

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

Work started at `141a62b7dabf8c827a737f217e87544fbfbc15b3`. Failing-test commit: `c177ff7`.

**Built**

- `src/pathly_orchestrator/pty_host/host.py`: `_child_env` pops `PATHLY_CHIEF_HOOK_SECRET` (after
  the run-token pop), with a comment why.
- `studio/src/main/ipc/terminal/chiefSecret.ts` (new): `isChiefClaudeSpawn(runId, argv,
  interactive)`, `claimChiefHookSecret(runId)` (tokenless `POST ${getApiBase()}/chief/hook-secret`
  `{run_id}` with `X-Pathly-Secret`; the secret on a 200 with a non-empty string, else null for any
  other status, bad body or network error), `chiefSecretForSpawn` (undefined when not a claude
  chief; throws when the claim fails, which refuses the spawn).
- `studio/src/main/ipc/terminal/spawnEnv.ts`: `buildSpawnEnv(cwd, meta, chiefHookSecret?)` deletes
  `PATHLY_CHIEF_HOOK_SECRET` for every child and sets it only from the third argument.
- `studio/src/main/ipc/terminal.ts`: `handleSpawn` awaits `chiefSecretForSpawn(runnerTabMeta.get(tabId)?.run_id,
  runnerArgv, !!initialInput)` after argv/shell resolution and before the gate (so a refused claim
  holds no slot), and passes it to `buildSpawnEnv`. 381 lines (under 400).
- `ChiefLauncher.tsx`: `SAME_USER_NOTE` shown when `l.cli === 'claude'`; `CODEX_NOTE` unchanged.
- Tests: new `tests/runner_supervisor/test_pty_host_strips_chief_secret.py` (6),
  new `chiefSecret.test.ts` (18), `spawnEnv.test.ts` (+3), `ChiefLauncher.test.tsx` (+2).
- Docs: `studio/CLAUDE.md` module table (`spawnEnv.ts` row, new `chiefSecret.ts` row) and the
  dependency line. `tests/INDEX.md`, `tests/runner_supervisor/INDEX.md` regenerated.

**Proof**

- `python -m pytest tests/runner_supervisor/test_pty_host_strips_chief_secret.py -q -p no:cacheprovider`:
  `6 passed`, exit 0 (at `c177ff7`: 4 failed, the env still held the made-up secret).
- `npm --prefix studio run test -- src/main/ipc/terminal/spawnEnv.test.ts src/main/ipc/terminal/chiefSecret.test.ts`:
  `2 passed (2)`, `24 passed (24)`, exit 0. Covers: non-chief child (no meta, `{}`, a run token,
  undefined/empty third arg) never gets the variable with Studio's own env holding one; a chief
  child gets exactly the claimed value and `process.env` keeps its own; 409/403/404/500, a network
  error and a 200 with no usable secret return null; a 409 or failed claim makes
  `chiefSecretForSpawn` throw (spawn refused); non-chief/codex/headless spawns claim nothing; the
  secret is in no console call. At `c177ff7`: chiefSecret.ts missing, 2 spawnEnv cases failed.
- `npm --prefix studio run test -- src/renderer/src/components/topbar/ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx`:
  `3 passed (3)`, exit 0 (claude shows the same-user line, not CODEX_NOTE; codex shows CODEX_NOTE,
  not the line). At `c177ff7`: the 2 new cases failed.
- `node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json`: exit 0.
  `npm --prefix studio run typecheck`: exit 0. `npm --prefix studio run test`: `45 passed (45)`
  files, `295 passed (295)`, exit 0.
- Also: `python -m pytest tests/consistency tests/runner_supervisor -q -x`: `540 passed`;
  `black --check` (after formatting the new test), `check_file_size.py` (none new, none grown),
  `gen_test_index.py --check`, bandit and mypy on `pty_host`: exit 0.

**Decisions**

- The chief check uses the original `runnerArgv[0] === 'claude'` (the bare name `ALLOWED_SHELLS`
  admits, before launcher resolution) and the runner meta's `run_id`, not the tab id.
- The claim runs before the concurrency gate, so a refused chief never takes an interactive slot.
- `chiefSecret.ts` imports `../../apiConfig` relatively: vitest has no `@main` alias.

**Shortcuts taken**: none.

**For later tickets**

- `src/pathly_orchestrator/CLAUDE.md` ("Where the secret lives", from 15's rework) still says that
  until ticket 18 nothing claims the secret; with this ticket Studio claims it on every claude
  chief spawn, so that sentence is now stale. It is outside this ticket's Touches; the next ticket
  that touches that doc (or a docs pass) should say Studio's main process claims it before the
  spawn, so a second (thieving) claim now closes the chief, while a claim that wins the race
  before Studio's makes Studio's 409 and the chief is refused and closed.
- Root `CLAUDE.md`'s `chief/` row still does not name `POST /chief/hook-secret` (noted by 15).
