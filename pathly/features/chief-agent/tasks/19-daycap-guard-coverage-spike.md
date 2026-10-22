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
