# Paste a chief's first prompt only when claude is ready, after its trust screen

Type: task
Status: open
Blocked by: 13
Test first: yes
Level: 3
Touches: studio/src/main/ipc/terminal/promptInjector.ts, studio/src/main/ipc/terminal/promptInjector.test.ts (new), studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt (new), studio/CLAUDE.md

Spike leftover S4: the first open of a never-trusted folder lost the chief's pasted prompt to
claude's folder-trust screen. Build ticket 13's answer to question 1: A, Studio answers the
screen and never pastes blind into a chief tab.

0. **Record the wording first.** Its only source is a user's quote in
   https://github.com/anthropics/claude-code/issues/40002 (map Decisions so far), so it is
   unmeasured. Write `studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt` (new): the
   screen's text as the installed claude prints it on a first interactive open of a fresh empty
   temporary folder (for example `script -qc claude /dev/null` under `timeout 15`, ANSI stripped,
   the folder deleted after), with a first line `# source: claude <claude --version>, captured
   <date>`. If no claude is installed or it cannot reach the trust screen (it asks to log in
   first), write the issue's quoted text instead with `# source: issue #40002, unmeasured`, and add
   one line to `learnings.md` saying which it is. The tests below read this fixture, so a person who
   captures the screen on their claude only replaces the file.

In `studio/src/main/ipc/terminal/promptInjector.ts`:

1. `TRUST_PROMPT_RE` also matches claude's current wording (the fixture): `Is this a project you
   created or one you trust` and `Yes, I trust this folder` (each, case-insensitive), besides the
   phrases it has.
   The headless dismisser (`attachHeadlessGateDismisser`) shares it, so a headless first run in a
   new folder stops hanging on the new wording too.
2. A **chief tab** is one whose `tabId` matches `^chief-[0-9a-f]{12}$` (`open_chief` sends
   `tab_id` = the run id). For a chief tab, `attachStartupHandling` never starts the 5-second
   `fallbackTimer`: the prompt is pasted only on claude's ready prompt (`> ` in the ANSI-stripped
   output after any startup screen was answered and the buffer reset). A trust screen seen and
   answered first is followed by that wait, so the paste can never land in the screen. Every
   other interactive tab keeps its fallback.
3. Each answer and each "no ready prompt yet" stays logged with `slog('gate', …)`, as today.

Note in `studio/CLAUDE.md` (the terminal spawn section) that a chief tab pastes only after
claude's ready prompt and how the trust screen is handled.

## Not in this ticket

- Writing `~/.claude.json`: not done (ticket 13 chose A).
- The hook secret on the chief's spawn: tickets 15 and 18.
- A real claude: the person confirms the screen's wording on their machine (map Open questions).

## Done when

- `npm --prefix studio run test -- src/main/ipc/terminal/promptInjector.test.ts` passes and covers,
  with a fake `IPty` (an `onData` emitter and a recorded `write`) and fake timers: a chief tab fed
  the fixture's text (its `#` line dropped) gets `\r`, then no
  paste before the ready
  prompt, even 30 seconds later, then one bracketed paste after `> ` arrives; a chief tab never
  pastes on the 5-second fallback; a non-chief interactive tab still pastes after 5 seconds; the
  old wording ("Do you trust the files in this folder") still matches; a headless tab answers the
  current wording once.
- The fixture's first line names its source:
  `python -c "print(open('studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt', encoding='utf-8').readline())"`
  prints `# source:`.
- The main-process typecheck passes
  (`node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json`).
- All existing Studio tests still pass (`npm --prefix studio run test`).

```check
$ npm --prefix studio run test -- src/main/ipc/terminal/promptInjector.test.ts
exit 0
prints passed
$ python -c "print(open('studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt', encoding='utf-8').readline())"
exit 0
prints # source:
$ node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ npm --prefix studio run test
exit 0
```

## Reference

- `pathly/features/chief-agent/spike19-part-b-report.md` § Surprises (first bullet), read-only
- `studio/src/main/ipc/terminal/spawnEnv.test.ts` (how a main-process module is tested with vitest)
- spec.md § Decisions ("The trust screen")

## Answer
