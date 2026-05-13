# agent-architecture-refactor — Architecture Proposal

## Current state

```
skill (build/review/test)
  └── calls scout-path (sub-skill)
        └── scout-path spawns scout/quick agents
              └── returns compressed findings to scout-path
                    └── scout-path returns to calling skill
```

Problems:
- Two context hops before findings reach the caller.
- scout-path.md is loaded into the calling skill's context window.
- Skills that call scout-path cannot control spawn parameters directly.

---

## Target state

```
skill (build/review/test)
  └── spawns scout agent directly (inline delegation block)
        └── scout returns findings directly to calling skill
```

Changes:
- Each skill that previously called scout-path now contains an inline delegation block
  matching the pattern already established in `team/review.md`.
- scout-path.md is marked standalone-only; it remains in the catalog for direct
  invocation by users but is no longer called by pipeline stages.

---

## Tester agent contract alignment

**Current:** tester.md has no subagent delegation section. tester YAML lists only `[builder]` in can_spawn.

**Target:** tester.md gains a delegation section (consistent with builder.md and reviewer.md) documenting `type: scout` and `type: quick` spawns. Both adapter YAMLs gain `[quick, scout, builder]` in can_spawn.

No behavioral change to the tester's existing `phase: analyze` and `phase: test` blocks — the new section is additive documentation of spawn authority already implied by those phases.

---

## team.md → orchestrator handoff

**Current:** team.md is a monolithic skill that contains the full FSM: argument parsing, feature detection, mode selection, nano mode, FSM operations, state recovery, entry stage override, routing, git commits, PROGRESS.md updates, and artifact archiving. All of this runs in a single growing context window.

**Target:** team.md becomes a thin launcher. It retains only the parts that require user interaction before the pipeline starts:
- Argument parsing
- Feature detection
- Mode selection
- Nano mode (intentional bypass — does not use FSM)

Everything else moves to orchestrator.md, which runs as a spawned agent with its own clean context window per invocation. The orchestrator already contains the core FSM loop and subagent routing table; this refactor adds the team-specific pieces it was missing.

**Why nano stays in team.md:** Nano mode is explicitly designed to bypass the FSM pipeline. It involves one user interaction (task description), spawns builder and reviewer directly, and exits. It has no STATE.json, no PROGRESS.md, no routing table. Moving it to orchestrator would be wrong — the orchestrator is an FSM engine, and nano has no FSM.

---

## Invariants preserved

- planner.md: no scout spawn (intentional design — codebase investigation is builder's domain).
- po.md: no scout/quick spawn (intentional design — PO uses web-researcher only).
- explorer.md: no agent spawning (hard rule — "Do NOT spawn additional agents").
- team/review.md: unchanged (reference pattern for the new spawn style).
