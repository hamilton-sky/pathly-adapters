# Show consult runs in the Monitor as their own category

Type: task
Status: resolved
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

Work started at 399633093da700cbbd3e971782e1b9d9ce911d09 (a tree-same merge of master on e451529).

- **Built**: `'consult'` added to the category union in `Monitor/EngineBoard/types.ts`, `CliMonitorBar/types.ts`, `types/global.d.ts` (both `category` fields), the cast in `TerminalSpawnListener.tsx`, `registerRunner` in `main/preload/index.ts`, the `terminal:register-runner` handler in `main/ipc/terminal.ts`, `runnerTabMeta` in `terminal/ptyRegistry.ts` and the engine record in `terminal/spawnGate.ts`. A fourth `CATEGORY_META` entry (`consult`, `Consults`, `role agents answering agents' questions`, `var(--orange)`) after `single`; the dock's `CATEGORY_ORDER` ends with `consult` and `categoryColor` maps it to `var(--orange)`. New test `Monitor/EngineBoard/constants.test.ts`. `studio/CLAUDE.md` names the set `flow | loop | single | consult`.
- **Proof**: `npm --prefix studio run test -- src/renderer/src/components/Monitor/EngineBoard/constants.test.ts`: 6 passed, exit 0 (at the test commit: 4 failed, 2 passed). `npm --prefix studio run typecheck`: exit 0. `node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json`: exit 0. `npm --prefix studio run test`: 44 files, 274 tests passed, exit 0.
- **Decisions**: `var(--orange)` (defined in `styles/tokens.css`; the other three are accent, purple, runtime). The test also checks the dock's colour equals the board's for every category, so the two copies cannot drift. The board's own `categoryColor` stays unexported, as it was.
- **Shortcuts taken**: two places outside Touches still know only three categories, harmlessly: `CategoryBadge.module.css` has no `[data-cat='consult']` rule (the badge renders with its base style, no category tint), and `CliMonitorBar/DockFilter/DockFilter.tsx`'s segment list has no `Consult` segment (consult rows show under `all`, not filterable alone). Worth a follow-up if consults get frequent.
- **For later tickets**: none affected.
