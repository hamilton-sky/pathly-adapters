# Paste a chief's first prompt only when claude is ready, after its trust screen

Type: task
Status: resolved
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

Work started at `31fb2df` (a merge of master on top of `869b2b5`, the commit the prompt named).
Test-only commit: the "14 failing test" commit (rebuilt after the fixture moved under `__tests__/`).

**Built**
- `studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt` (new): the trust screen as the
  installed claude printed it, `# source: claude 2.1.319 (Claude Code), captured 2026-11-07`.
  Captured by running `/opt/node22/bin/claude` in a fresh empty temp folder with `env -i` (PATH,
  a fresh temp `HOME` holding only `{"hasCompletedOnboarding":true,"theme":"dark"}`, TERM; none of
  our credentials, no `--dangerously-skip-permissions`), killed after 15 s, folder deleted. It did
  not ask to log in; it showed the theme picker until the onboarding flag was set.
- `studio/src/main/ipc/terminal/promptInjector.ts`: `TRUST_PROMPT_RE` adds `Is this a project you
  created or one you trust` and `Yes, I trust this folder` (case-insensitive, `\s*` between
  words); the trust answer is written 1 s after the screen is seen, Down + Enter when the cursor
  sits on "No, exit", else Enter (headless dismisser and interactive injector both); the ready
  prompt is `> ` or `❯` + space/no-break space (not `❯ 1.`); a chief tab (`^chief-[0-9a-f]{12}$`)
  never starts the blind paste, it logs `no ready prompt yet: chief tab waits for it (no blind
  paste)` at 5 s; other interactive tabs log `no ready prompt yet: pasting on the 5 s fallback`
  and paste; screen text re-drawn after the answer is cut off before the ready check.
- `studio/src/main/ipc/terminal/promptInjector.test.ts` (new): 11 tests, fake `IPty` + fake timers.
- `studio/CLAUDE.md`: the `promptInjector.ts` row of the CLI-engine spawn scheduler table.

**Proof**
- `npm --prefix studio run test -- src/main/ipc/terminal/promptInjector.test.ts`: exit 0,
  `Tests 11 passed (11)`. Covers: a chief tab fed the fixture (its `#` line dropped) gets
  `\x1b[B\r` (ends in `\r`), no paste after a re-drawn screen and 30 s more, then exactly one
  bracketed paste after `> `; the same screen sent as the PTY really sends it (no spaces); the
  measured ready prompt `❯\u00a0`; a chief tab writes nothing in 60 s with no ready prompt and logs
  "no ready prompt yet"; a non-chief tab pastes at exactly 5 s; only `chief-<12 lowercase hex>`
  counts as a chief; the old wording "Do you trust the files in this folder" still matches
  (interactive and headless, Enter); the issue-quoted wording with the cursor on Yes gets Enter; a
  headless tab answers the current wording once. At `ec0063c` (test only) 7 of 11 failed.
- `python -c "print(open('studio/src/main/ipc/terminal/__tests__/claude-trust-screen.txt', encoding='utf-8').readline())"`:
  exit 0, prints `# source: claude 2.1.319 (Claude Code), captured 2026-11-07 (...)`.
- `node studio/node_modules/typescript/bin/tsc --noEmit -p studio/tsconfig.node.json`: exit 0
  (`npm --prefix studio run typecheck` too).
- `npm --prefix studio run test`: exit 0, `Test Files 43 passed (43)`, `Tests 268 passed (268)`.
- `python3 scripts/check_file_size.py`: OK (promptInjector.ts is 212 lines).
- Extra, outside the Done when: the module bundled with esbuild and run on the real claude 2.1.319
  through node-pty (same throwaway HOME, tab `chief-0123456789ab`): `+1530ms write "\x1b[B\r"`,
  `+1776ms` bracketed paste, `hasTrustDialogAccepted` true, the prompt in claude's input. The
  base version of the file on the same run: no answer, blind paste at `+5005ms`, folder not
  trusted, prompt lost (spike S4 reproduced).

**Decisions**
- The ticket says the chief tab "gets `\r`". Measured on claude 2.1.319, the screen opens with
  its cursor on "No, exit" (binary: `cancelFirst:!0, focus:"cancel", hideIndexes:!0`), and a bare
  Enter makes claude exit 1. So the answer is Down + Enter in one write when the cursor sits on
  "No, exit", and plain Enter otherwise (the old wording and the issue's quote put it on Yes).
- The screen refuses keys for its first moment (Down + Enter at 0 s and 0.1 s were ignored; 0.2 s
  and later worked), so the answer waits 1 s after the screen is first seen; the keys are chosen
  from the buffer at that moment, when the options are drawn.
- The ticket says the ready prompt is `> `. Current claude draws `❯` + U+00A0, never `> `, so with
  `> ` alone a chief would wait forever. The ready check takes both; it applies to every
  interactive tab, so non-chief tabs now paste on the ready prompt before the 5 s fallback too.
- The current screen positions each word with a cursor-column escape, so the ANSI-stripped stream
  has no spaces ("Isthisaproject..."): the new phrases match with `\s*`. The fixture shows the
  columns as spaces so a person can read and replace it.

**Shortcuts taken**
- The answer keys depend on the `❯` cursor glyph before "No, exit". If a later claude changes the
  glyph or the option order, the answer falls back to Enter (which may exit claude); the fixture
  plus these tests are the place to re-measure. A chief whose claude never shows a recognised ready
  prompt (a login screen, a new prompt glyph) gets no paste at all: safe (nothing is lost, the
  person sees the screen), but the chief starts empty.
- The 1 s answer delay is a margin over a measured ~0.2 s refusal window, not a contract.

**For later tickets**
- Ticket 12/18 and the person's confirmation (map Open questions): the trust screen was measured
  here on claude 2.1.319; the person still confirms on their own claude and replaces the fixture if
  it differs. `studio/CLAUDE.md` line "The chief's prompt is still auto-submitted" stays true.

