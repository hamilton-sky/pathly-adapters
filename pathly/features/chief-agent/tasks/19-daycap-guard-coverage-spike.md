# Spike: what does daycap's guard actually cover over Pathly spawns?

Type: task
Status: open
Blocked by: 21
Test first: no (spike; the finding is the deliverable)

daycap's `--guard` is a PreToolUse hook for interactive Claude Code / Codex
sessions: it reads the cached snapshot and can deny *tool calls inside a
session* (fail-open on stale/timeout; `src/bin/guard.js`, invariants 1-4).
The round-two draft `round-two-drafts/daycap-spend-report.md` (round-one
ticket 18 until 2026-10-14) wires daycap as a *reporting* source. This spike
stays in round one because it changes no code and blocks nothing. Before
anyone treats daycap
as an *enforcement* backstop for the fleet, this spike must answer one
question with a real run:

**Does the guard fire on Pathly's headless spawns?**

Pathly spawns `claude -p '{prompt}' --model ... --output-format json
--dangerously-skip-permissions` as a subprocess (see root `CLAUDE.md`,
Studio CLI spawn scheduler). Two sub-questions:

1. Does a headless `-p` session load the user's `settings.json` hooks at
   all (i.e. does the guard even get consulted)?
2. If it does, does `--dangerously-skip-permissions` bypass the PreToolUse
   decision (making the guard a no-op for exactly the spawns Pathly makes)?

One answer is already known: the guard does **not** run in the chief tab.
The chief starts with `--restricted` (or `--setting-sources` with
no sources), which ignores the user's `settings.json`, where daycap installs
its hook (spec.md § Decisions, "The chief's claude permissions"). Once
the chief can be opened, confirm it with the chief open and over
budget, and record it with the rest.

Procedure: install the daycap guard on the dev machine, set a tiny daily
budget, trigger it over budget, then run one headless spawn exactly as
`supervisor/terminal.py` builds it and observe whether the spawn or its
tool calls are denied. Record the exact CLI version — hook behavior is
version-sensitive. Also record what the over-budget spawn cost: a guard that
denies tool calls does not stop the model taking turns, so the spawn keeps
spending until it gives up.

## Outcome A: the guard fires on headless spawns

Then daycap is a fleet-wide brake and Pathly gets it for free. It is not a
kill switch: it denies tool calls, not tokens, so a denied spawn still spends
until it gives up (the cost recorded above says how much).

- Living doc: one paragraph in `src/pathly_orchestrator/CLAUDE.md`
  ("daycap is the machine-wide backstop; the chief's per-session ceilings are the
  Pathly-aware inner layer").
- Optional hardening (only if cheap): the supervisor reads the daycap
  snapshot before spawning and skips the spawn when over budget — fail open
  on stale/missing, so a daycap outage never wedges the fleet.
- The chief's text (the `chief-connect` fragment) may say
  "daycap can block agents' tool calls machine-wide when the daily budget is
  gone"

## Outcome B: the guard does not fire on headless spawns

Then the boundary is explicit and must be written down, not assumed:

- daycap covers the human's own **interactive** sessions. It does **not**
  cover Pathly's headless fleet, and it does not cover the chief tab, which
  loads no user settings. Putting the guard in the chief's own
  settings file would be a round-two decision.
- Headless enforcement stays Pathly-side: the chief's per-session ceilings
  (spec.md § Decisions, "Limits")
  plus the per-goal `cost_cap.py`. If a machine-wide daily stop for the
  fleet is wanted, it needs a Pathly-side daily accumulator (new ticket —
  do not bolt it onto this one).
- Record the boundary in the living doc and in `learnings.md` (one line,
  tagged with this ticket number), so nobody re-derives it in six months.

Either way, this ticket changes no enforcement code. Its deliverable is the
measured answer plus the doc line. Do not build Outcome A's optional
hardening inside this ticket.

## Part B: does a real chief session work the way the code says?

Added 2026-10-22 at the person's request (they chose to extend this spike). Every chief test uses a
fake spawn host. Nothing has yet run a real `claude` against what the chief depends on, and no other
ticket plans it. This part is one short live session in the same sitting as part A. Its deliverable is
a measured yes or no per question, not code.

Setup: the Pathly server runs from master with tickets 20 and 21 merged, `claude` is installed and
signed in, and a scratch project folder has a git repo and one feature folder. Studio has no chief
launcher yet, so open an operator chief by calling `POST /chief/open` directly. Pathly pastes the
style and the fixed rules into the new tab and the person presses Enter. Record the exact claude CLI
version. The person runs this on their own machine (through a Remote Control session if one is
available), and the builder of this ticket only writes down what was observed.

Answer each question yes or no, with the command and what it printed:

1. Restricted start. Ask the chief to run `ls`, `git status`, `curl http://127.0.0.1:8765/health`
   and `python3 -c "print(1)"`. Only `pathly *` runs without asking; curl and wget are denied; any
   other command asks.
2. Switches. With `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and `CLAUDE_CODE_DISABLE_CRON=1` in the
   chief's settings (ticket 20, B1), a background command and a `.claude/scheduled_tasks.json` entry
   produce no prompt in the tab.
3. Hook. A message the person types in the tab is recorded by the `UserPromptSubmit` hook as a
   `human` row with a message number the chief can cite (read it in the database or by the route the
   docs name).
4. `pathly api`. Inside the tab the chief reads `GET /chief/session?project_root=<root>` and posts
   with `POST /comms/post`; the posted row carries the chief's stamp.
5. Cited answers end to end. Get a headless agent to ask the person a question (the way
   `src/pathly_orchestrator/CLAUDE.md` "Cited answers" describes). The person types the answer in the
   chief tab. The chief answers with `cite`; the agent receives the person's exact words. An answer
   without a cite is refused (403) and does not reach the agent.
6. Limits. Set `chief.max_runs_per_session` to 2 and ask the chief for three runs. The third is
   refused, no run starts, and the chief tells the person.
7. The texts. The built-in operator style plus the fixed rules lead a real claude to sensible first
   commands: read the session, `GET /comms` with board, scope and feature, no curl. Record anything it
   gets wrong.
8. Close. `POST /chief/close` ends the tab and the chief's token stops working (a `pathly api` call
   from a shell that still holds it answers 401).

Every "no" is recorded in the Answer under `For later tickets` as a proposed ticket. Do not fix a
finding inside this ticket.

Part B adds to Done when: the Answer has a yes or no with evidence for each of questions 1 to 8 and
the CLI version; the known-limit sentence in the `(chief-agent)` entry of `CHANGELOG.md` ("no
automated test opens a real claude" and the sentence naming this spike) says what was measured and
what stays unmeasured; `learnings.md` gains one line, tagged with this ticket number, for each
surprising finding.

## Not in this ticket

- Changing the guard, the spawn argv, or any ceiling.
- The reporting integration: `round-two-drafts/daycap-spend-report.md`
  (independent of this outcome).

## Done when

- The `## Answer` section records: CLI version tested, whether the guard
  fired at spawn and/or on in-session tool calls, what the over-budget spawn
  cost, which outcome (A/B) held, and the doc line that was added.
- `learnings.md` gains the one-line boundary note.

## Reference

- spec.md § Decisions: "The chief's claude permissions" (restricted start), "Limits"
  (session ceilings),
  `round-two-drafts/daycap-spend-report.md` (daycap reporting)
- daycap `src/bin/guard.js` (invariants 1-4, fail-open design),
  `src/bin/daycap.ts` (`install --guard`)
- `src/pathly_orchestrator/supervisor/terminal.py` (spawn construction),
  `src/pathly_orchestrator/adapters.py` (`_dash_safe_prompt`, headless argv)

## Answer
