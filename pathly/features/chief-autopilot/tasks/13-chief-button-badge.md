# Show the unread notices on the Chief button, and say what a codex chief cannot promise

Type: task
Status: open
Blocked by: 08
Test first: yes
Level: 2
Touches: studio/src/renderer/src/services/chiefApi.ts, studio/src/renderer/src/components/topbar/ChiefButton/, studio/CLAUDE.md

Spike S13 part 1, Studio half (ticket 08 is the server half), and the review's m3.

1. `studio/src/renderer/src/services/chiefApi.ts`: `getChiefNotices(projectRoot)` and
   `markChiefNoticesRead(projectRoot, runIds)` for ticket 08's two routes.
2. `ChiefButton` polls `getChiefNotices` for the selected project every 15 s while the window is
   focused (a hook in `ChiefButton/hooks/`), and shows the unread count as a badge. Opening the
   menu lists them (run, status, error, cost, questions waiting) and marks them read.
3. `ChiefLauncher`: next to the engine choice, a one-line note when `codex` is picked that a codex
   chief can read files outside the project and is not safe to leave alone yet.

Living docs: `studio/CLAUDE.md` for the badge and the note.

## Not in this ticket

- The autopilot switch and budget fields in the launcher: round four.

## Done when

- `npm --prefix studio run test -- ChiefButton` passes with tests that a non-zero unread count
  shows the badge, zero shows none, opening the menu calls `markChiefNoticesRead` with the listed
  run ids, and picking `codex` in the launcher shows the note.
- `npm --prefix studio run typecheck` exits 0.

```check
$ npm --prefix studio run test -- ChiefButton
exit 0
$ npm --prefix studio run typecheck
exit 0
```

## Reference

- spec.md § Stories ("Know when a run ends", the codex note)
- `studio/src/renderer/src/components/topbar/ChiefButton/chiefLauncherUtils.test.ts` (test shape)

## Answer
