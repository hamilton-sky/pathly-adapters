# Pathly — Suggestions & Improvements

_A consolidated, actionable roadmap of every improvement recommended for the
Pathly agents & skills system. Companion to `PATHLY_ASSESSMENT.md` (which holds
the full analysis and issue diagnoses)._

---

## How to read this file

- **Fix** = corrects something currently wrong (drift, inconsistency, typo).
- **Enhancement** = adds value beyond the current design.
- **Effort**: S (hours) · M (a day) · L (multi-day).
- **Impact**: ★ low · ★★ medium · ★★★ high.

---

## A. Correctness fixes ✅ ALL DONE (2026-05-24)

### A1 — Unify the storage path: `plans/` vs `pathly/plans/`  ·  ✅ DONE

~~The single most important change.~~ Fixed: 39 files updated to use `pathly/plans/`,
`pathly/explorations/`, `pathly/debugs/` throughout `core/skills/` and `core/agents/`.
Studio Monitor now finds STATE.json for all flows.

- [x] Pick one canonical root — `pathly/` (namespaced).
- [ ] ~~Define a documented `STORAGE_ROOT` constant~~ — still a nice-to-have
- [x] Sweep all of `core/skills/` and `core/agents/` to the single prefix.
- [ ] Add a CI grep that fails the build on the wrong prefix — covered by B1

### A2 — Reconcile `team-flow/` vs `team/` naming  ·  ✅ DONE

Fixed: all `team-flow` references replaced with `team` across SKILLS_OVERVIEW,
director, README_routing, po, and pipeline templates. Zero occurrences remain.

- [x] Keep the directory `team/` (less churn, no adapter changes).
- [x] Update all `team-flow/` doc references to `team/`.

### A3 — De-duplicate the director routing logic  ·  ✅ DONE

Fixed: `go.md` is now the single source. `director.md` Decision Rules block
replaced with a reference to `go.md`. `pathly.md` Behavior: go collapsed to a
two-line delegation.

- [x] Make `go.md` the single source for the routing procedure.
- [x] Slim `director.md` to the role contract; reference `go.md` for the decision table.
- [x] Replace the inlined "Behavior: go" in `pathly.md` with a delegation.

### A4 — Relocate `director` out of `planning/`  ·  ✅ DONE

Fixed: `agents/planning/director.md` moved to `agents/director.md`.

- [x] Move to top-level `agents/` directory.

### A5 — Rename typo'd directory `skills/team/pathly-controlls/`  ·  ✅ DONE

Fixed: directory deleted (it was empty, containing only `.gitkeep`).

- [x] Deleted unused `pathly-controlls/` directory.

---

## B. Guardrails against future drift

### B1 — Add a `core/` consistency checker  ·  Enhancement · P1 · ★★★ · M

The root cause behind A1–A3. `SKILLS_OVERVIEW.md` is hand-maintained and has
already slipped. A script + CI step should verify:

- [ ] Every skill referenced in docs exists on disk.
- [ ] No file references a path prefix outside the canonical `STORAGE_ROOT`.
- [ ] Every `core/skills/*.md` has matching `_meta` entries in **each** adapter
      (claude/codex/copilot).
- [ ] Doc cross-references resolve to real files.

### B2 — Schema for the feedback-file protocol  ·  Enhancement · ★★ · M

- [ ] Add a JSON schema (or documented spec) for `STATE.json`, `EVENTS.jsonl`,
      and each feedback-file type so contracts can be validated, not just read.
- [ ] Wire the schema into the checker (B1).

### B3 — Generate, don't hand-write, the skill map  ·  Enhancement · ★★ · M

- [ ] Auto-generate the "Skill Map — Who Does What" section of
      `SKILLS_OVERVIEW.md` from the actual files, removing the manual-sync
      footer obligation.

---

## C. Behavioral assurance

### C1 — Golden-path transcript tests per skill  ·  Enhancement · ★★★ · L

Catch prompt drift the way unit tests catch code drift.

- [ ] For each skill: define representative inputs → expected routing/decision.
- [ ] Run them in CI against the contracts so a prompt edit that breaks routing
      fails the build.

### C2 — Adapter parity tests  ·  Enhancement · ★★ · M

- [ ] Assert that every core skill/agent materializes correctly for all three
      hosts (stitched output validates against expected frontmatter).

---

## D. Product / UX enhancements

### D1 — Close the lessons loop automatically  ·  Enhancement · ★★ · M

`retro → LESSONS_CANDIDATE.md → lessons → LESSONS.md → planner injection` is a
strong feedback loop, but it depends on a human running `lessons`.

- [ ] Surface candidate lessons automatically at `end`/`archive` time and prompt
      to promote them.

### D2 — FSM observability (timeline + cost)  ·  ✅ DONE (already in Studio)

`Monitor/FsmView.tsx` (pipeline stepper), `Monitor/EventLog.tsx` (live SSE stream),
and `PlanBoard.tsx` (per-conversation token + cost rollups) already cover this at
the conversation level. Optional: add a flow-level cost summary if a single
"what did this feature cost?" number is wanted.

- [x] Studio Monitor shows FSM timeline and per-event cost.

### D3 — Guided first-run that hides the machinery  ·  Enhancement · ★★ · M

The full vocabulary (rigor levels, feedback files, FSM states) is heavy for
newcomers; `nano` helps but the concepts still surface early.

- [ ] A guided first-run / progressive-disclosure mode that reveals advanced
      machinery only when needed, lowering the adoption barrier.

### D4 — Self-doctor surface  ·  Enhancement · ★ · S

`help --doctor` and `verify-state` already exist.

- [ ] Have the checker (B1) power a user-facing "is my Pathly install/state
      healthy?" command that reports drift and stale files in plain language.

---

## E. Suggested sequencing

```
Phase 1 (correctness)   : ✅ A1 → A2 → A3 → A5 → A4   DONE 2026-05-24
Phase 2 (hold the line) : B1 → B2 → B3
Phase 3 (assurance)     : C1 → C2
Phase 4 (product value) : D2 ✅ → D1 → D3 → D4
```

Phase 1 is complete. Phase 2 prevents the same drift from returning.
Phases 3–4 are where the system goes from "well-designed" to "trustworthy and pleasant to adopt."

---

## F. One-line rationale per recommendation

| ID | Recommendation | Why it matters |
|----|----------------|----------------|
| A1 | Unify storage path | Prevents silent state loss / missed features |
| A2 | Fix `team-flow/` refs | Docs must point at real files |
| A3 | De-dup director logic | Stops the drift that A1/A2 are symptoms of |
| A4 | Relocate `director` | Structure should reflect the architecture |
| A5 | Fix `controlls` typo | Hygiene |
| B1 | Consistency checker | Automates what manual discipline keeps failing |
| B2 | Protocol schema | Makes contracts validatable |
| B3 | Generate skill map | Removes a standing sync obligation |
| C1 | Transcript tests | Catches prompt drift like code tests catch bugs |
| C2 | Adapter parity tests | Guarantees all hosts stay in sync |
| D1 | Auto lessons loop | Realizes the learning loop without manual steps |
| D2 | FSM observability | Makes behavior legible; builds user trust |
| D3 | Guided first-run | Lowers the adoption barrier |
| D4 | Self-doctor | Turns internal checks into user value |
