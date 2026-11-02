# Show the unread notices on the Chief button, and say what a codex chief cannot promise

Type: task
Status: resolved
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

**Built** (work started at 76dfdc1c, the merge after 00cea4f8 that brought ticket 08 in; failing
test ab1d5848):
- `studio/src/renderer/src/services/chiefApi.ts`: `ChiefNotice` type, `getChiefNotices(projectRoot)`
  (`GET /chief/notices`, list or null) and `markChiefNoticesRead(projectRoot, runIds)`
  (`POST /chief/notices/read`, the `marked` count or null). Both fail soft like the other reads.
- `ChiefButton/hooks/useChiefNotices.ts` (new): reads on mount / project change, every 15 s while
  `document.hasFocus()`, and on window `focus`; `markRead` drops the ids locally, then posts.
- `ChiefButton/ChiefNotices/ChiefNotices.tsx` + `.module.css` (new): list "Finished chief runs"
  (kind · run id, status, `$cost`, "N questions waiting", error).
- `ChiefButton/ChiefButton.tsx` + `.module.css`: badge `topbar-chief-badge` with the unread count
  (none at zero; the count is also in the trigger's aria-label); opening the popover snapshots the
  notices, shows them above the launcher and marks those run ids read.
- `ChiefButton/ChiefLauncher/ChiefLauncher.tsx`: when the engine is `codex`, the footer note (right
  under ENGINE) adds "A codex chief can read files outside the project, so it is not safe to leave
  alone yet."
- Tests: `ChiefButton/ChiefButton.test.tsx` (3), `ChiefButton/ChiefLauncher/ChiefLauncher.test.tsx` (1).
- `studio/CLAUDE.md`: Chief launcher paragraph (routes, codex note, Notices); "no inbox count yet" removed.

**Proof**:
- `npm --prefix studio run test -- ChiefButton`: exit 0, 3 files, 11 tests passed (badge shows 2;
  zero shows none; opening lists run-a/run-b with error, $1.25, "2 questions waiting" and calls
  `markChiefNoticesRead('/work/proj', ['run-a','run-b'])`, badge gone; picking Codex shows the note).
  At ab1d5848 the 4 new tests failed (no badge element, no note text) and the 7 old ones passed.
- `npm --prefix studio run typecheck`: exit 0.
- `npm --prefix studio run test` (full): 42 files, 257 tests passed, exit 0.
- `python3 scripts/check_file_size.py`: "none new, none grown", exit 0. Studio has no lint script.

**Decisions**:
- The list shows the snapshot taken when the popover opens, so the runs stay visible after they are
  marked read; the badge clears at once (local drop), and a failed mark comes back on the next poll.
- Focus gating: the interval skips while the window lacks focus, and a `focus` event reads at once,
  so a returning person sees the count without waiting 15 s.
- The codex note sits in the launcher's existing `footerNote` (directly under the ENGINE section):
  `PromptActionConfig` is outside Touches, so no slot beside the picker itself.

**Shortcuts taken**: none.

**For later tickets**: `useChiefNotices` is the one reader of `/chief/notices` in Studio; round
four's notice in the chief's tab should reuse `chiefApi.getChiefNotices`.
