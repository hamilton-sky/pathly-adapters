# Show consult runs in the Monitor as their own category

Type: task
Status: open
Blocked by: 16
Test first: yes
Level: 3
Touches: studio/src/renderer/src/components/Monitor/EngineBoard/types.ts, studio/src/renderer/src/components/Monitor/EngineBoard/constants.ts, studio/src/renderer/src/components/Monitor/EngineBoard/constants.test.ts (new), studio/src/renderer/src/components/CliMonitorBar/types.ts, studio/src/renderer/src/components/CliMonitorBar/constants.ts, studio/src/renderer/src/types/global.d.ts, studio/src/renderer/src/components/TerminalSpawnListener.tsx, studio/src/main/preload/index.ts, studio/src/main/ipc/terminal.ts, studio/src/main/ipc/terminal/ptyRegistry.ts, studio/src/main/ipc/terminal/spawnGate.ts, studio/CLAUDE.md

"Consult spawns ... appear in the Monitor like any other run, with their own run category." Ticket
16 stamps `consult` on the spawn payload's `category`, the `AGENT_DONE` and the
`agent_invocations` row; Studio knows only `'flow' | 'loop' | 'single'`, so today a consult run
lands in no Monitor section (`CATEGORY_META` has no entry) or is cast to a wrong one.

Add `'consult'` to every copy of the category union: `EngineCategory` in
`studio/src/renderer/src/components/Monitor/EngineBoard/types.ts` and
`studio/src/renderer/src/components/CliMonitorBar/types.ts`, the `category` fields in
`studio/src/renderer/src/types/global.d.ts`, the cast in `TerminalSpawnListener.tsx`,
`registerRunner` in `studio/src/main/preload/index.ts`, the `terminal:register-runner` handler in
`studio/src/main/ipc/terminal.ts`, `runnerTabMeta` in `studio/src/main/ipc/terminal/ptyRegistry.ts`
and the record in `studio/src/main/ipc/terminal/spawnGate.ts`.

Then give it a place: a fourth `CATEGORY_META` entry (`key: 'consult'`, label `Consults`, blurb
`role agents answering agents' questions`, colour a design-system variable not used by the other
three, e.g. `var(--orange)`), after `single`, and the dock's `CATEGORY_ORDER` and
`categoryColor` in `studio/src/renderer/src/components/CliMonitorBar/constants.ts`. Controls stay those of `single` (open / stop):
`controlsForEngine` already treats every non-`flow` category that way. `RunDetailPage`'s
`KindBadge` takes any string, so `kind: consult` from `GET /runs` needs no change.

Note in `studio/CLAUDE.md` that the category set is `flow | loop | single | consult`.

## Not in this ticket

- Server-side category: ticket 16. Kind `consult` in `GET /runs`: ticket 09, server side.
- A Monitor control specific to consults (for example "show the question"): not needed for the bar.

## Done when

- `npm --prefix studio run test -- src/renderer/src/components/Monitor/EngineBoard/constants.test.ts`
  passes and covers: `CATEGORY_META` has the four keys in the order flow, loop, single, consult,
  each with a distinct colour; `categoryColor('consult')` is that colour; the dock's
  `CATEGORY_ORDER` ends with `consult`.
- `npm --prefix studio run typecheck` and the main-process typecheck
  (`node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json`) both pass.
- All existing Studio tests still pass (`npm --prefix studio run test`).

```check
$ npm --prefix studio run test -- src/renderer/src/components/Monitor/EngineBoard/constants.test.ts
exit 0
prints passed
$ npm --prefix studio run typecheck
exit 0
$ node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ npm --prefix studio run test
exit 0
```

## Reference

- spec.md § Decisions ("Consult run identity")
- `studio/CLAUDE.md` (typecheck commands, IPC pattern)

## Answer
