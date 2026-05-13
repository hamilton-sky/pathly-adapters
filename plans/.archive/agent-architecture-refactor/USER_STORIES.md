# agent-architecture-refactor — User Stories

---

## S1 — Scout-pattern migration

### S1.1 — Skill files call scout agent directly, not via scout-path

As a pipeline stage (build, review, test, explore),
I want to spawn the scout agent inline rather than delegating through scout-path,
so that context research does not require an extra indirection layer that bloats context.

**Delivered by:** Conv 1

**Acceptance criteria:**
- AC1: The string `scout-path` does not appear in `build.md`, `review.md`, `test.md`, `explore.md`, `team/build.md`, `team/test.md`, or `team/plan.md` as an instruction to call or invoke anything.
- AC2: Each of those seven files contains a `Spawn **scout** agent` instruction in place of the former scout-path call.
- AC3: `team/plan.md` Storm Phase 2 and Plan Phase 2 spawn one scout per NEEDS_CONTEXT entry in parallel by default — up to 4 simultaneous scouts (matching the NEEDS_CONTEXT cap of 4); sequential only when entry B's question explicitly references entry A's answer (e.g. "that class", "the above").
- AC4: `team/review.md` is not modified (it is already correct and serves as the reference pattern).

**Edge cases:**
- A file may reference `scout-path` in a comment or docstring explaining history; this is acceptable as long as the invocation instruction itself is replaced.
- Scope overlap between entries is not a dependency — scouts are read-only, two scouts can read the same files with different questions simultaneously.

---

### S1.2 — scout-path.md is marked standalone-only; discover.md subagents table updated

As a developer reading the skill catalog,
I want `scout-path.md` to clearly state it is for standalone use only and that the pipeline uses direct agent spawns,
so that future contributors do not reintroduce skill-in-skill calls.

**Delivered by:** Conv 1

**Acceptance criteria:**
- AC1: `scout-path.md` contains a note stating it is for standalone invocation only and that pipeline stages spawn the scout agent directly.
- AC2: `team/discover.md` subagents table no longer references `scout-path` as the mechanism; it describes the direct spawn pattern instead.

---

## S2 — Worker agent parity (tester + builder)

### S2.1 — tester.md has a scout spawn section matching the builder/reviewer pattern

As a tester agent instance,
I want a documented delegation pattern for spawning scout and quick agents,
so that I can gather codebase context before verifying acceptance criteria in the same way builder and reviewer do.

**Delivered by:** Conv 2

**Acceptance criteria:**
- AC1: `tester.md` contains a subagent delegation section (titled or structured consistently with how builder.md and reviewer.md document their scout spawn patterns).
- AC2: The section documents spawning `type: scout` for multi-file test infrastructure investigation and `type: quick` for single-file lookups.
- AC3: The section does not override or contradict the existing `phase: analyze` block already in `tester.md`.

---

### S2.2 — builder.md delegation pattern upgraded with way of thinking and constraints

As a builder agent instance,
I want my scout delegation pattern to include `way of thinking` and `constraints` fields,
so that scouts I spawn receive the same sharp framing that reviewer.md and architect.md already provide.

**Delivered by:** Conv 2

**Acceptance criteria:**
- AC1: `builder.md` scout delegation block contains a `way of thinking` field describing the builder's lens (implementation patterns, utility functions, naming conventions).
- AC2: `builder.md` scout delegation block contains a `constraints` field (read only, do not suggest fixes, stay within stated scope).
- AC3: No other content in `builder.md` is changed.

---

### S2.3 — tester YAML can_spawn includes quick and scout

As an adapter host (claude or codex),
I want the tester YAML to declare `can_spawn: [quick, scout, builder]`,
so that the host enforces correct agent spawn permissions at runtime.

**Delivered by:** Conv 2

**Acceptance criteria:**
- AC1: `src/pathly_data/adapters/claude/_meta/tester.yaml` contains `can_spawn: [quick, scout, builder]`.
- AC2: `src/pathly_data/adapters/codex/_meta/tester.yaml` contains `can_spawn: [quick, scout, builder]`.
- AC3: No other field in either YAML file is changed.

---

### S2.4 — planner.md gains full scout spawn access

As a planner agent instance,
I want to spawn scout and quick agents to investigate the current codebase before writing stories and plans,
so that plans accurately reflect existing architecture, patterns, and integration boundaries rather than being written blind.

**Delivered by:** Conv 2

**Acceptance criteria:**
- AC1: `planner.md` contains a scout delegation section with `way of thinking` scoped to understanding existing state (not making implementation decisions).
- AC2: The section documents `type: scout` for cross-file architecture investigation and `type: quick` for single-file lookups.
- AC3: The existing rule "Planner does not spawn scouts — codebase investigation is builder's domain" is removed.
- AC4: No other content in `planner.md` is changed.

---

### S2.5 — planner YAML can_spawn includes scout

As an adapter host (claude or codex),
I want the planner YAML to declare `can_spawn: [quick, scout, web-researcher]`,
so that the host enforces correct agent spawn permissions at runtime.

**Delivered by:** Conv 2

**Acceptance criteria:**
- AC1: `src/pathly_data/adapters/claude/_meta/planner.yaml` contains `can_spawn: [quick, scout, web-researcher]`.
- AC2: `src/pathly_data/adapters/codex/_meta/planner.yaml` contains `can_spawn: [quick, scout, web-researcher]`.
- AC3: No other field in either YAML file is changed.

---

## S3 — Explorer agent parity

### S3.1 — explorer.md gains scout spawn section and removes no-spawn hard rule

As an explorer agent instance,
I want to be able to spawn scout agents mid-trace when I hit gaps beyond my 5-file read budget,
so that deep codebase traces are not limited by an arbitrary file count.

**Delivered by:** Conv 3

**Acceptance criteria:**
- AC1: `explorer.md` contains a scout spawn delegation section consistent with builder.md/reviewer.md structure.
- AC2: The hard rule "Do NOT spawn additional agents" is removed from `explorer.md`.
- AC3: The delegation section states scouts are terminal and read-only (explorer remains read-only on production code).
- AC4: No other content in `explorer.md` is changed.

---

### S3.2 — explorer YAML can_spawn includes scout and quick

As an adapter host (claude or codex),
I want the explorer YAML to declare `can_spawn: [scout, quick]`,
so that the host enforces correct agent spawn permissions at runtime.

**Delivered by:** Conv 3

**Acceptance criteria:**
- AC1: `src/pathly_data/adapters/claude/_meta/explorer.yaml` contains `can_spawn: [scout, quick]`.
- AC2: `src/pathly_data/adapters/codex/_meta/explorer.yaml` contains `can_spawn: [scout, quick]`.
- AC3: No other field in either YAML file is changed.

---

## S4 — Orchestrator conversion

### S4.1 — team.md becomes a thin launcher that spawns the orchestrator agent

As a user running `/team <feature>`,
I want `team.md` to parse arguments, detect the feature, handle nano mode, and then spawn the orchestrator agent with full context,
so that the FSM runs inside the orchestrator's clean context window rather than accumulating across the entire team.md session.

**Delivered by:** Conv 4

**Acceptance criteria:**
- AC1: `team.md` retains all argument parsing, feature detection, mode selection, and nano mode sections unchanged.
- AC2: `team.md` replaces the FSM operations, state recovery, routing table, git commit, PROGRESS.md update, and artifact archiving sections with a single orchestrator spawn instruction.
- AC3: The spawn instruction passes `FEATURE`, `rigor`, `autoFlow`, and `entryStage` to the orchestrator agent.
- AC4: `team.md` no longer contains the routing table (`| FSM state | Sub-skill |`).

**Edge cases:**
- Nano mode must remain inline in `team.md` — it must not be delegated to orchestrator (it is intentionally thin and does not use FSM stages).

---

### S4.2 — orchestrator.md gains git commit, PROGRESS.md update, and team pipeline routing table

As an orchestrator agent,
I want my contract to include the git commit instructions, PROGRESS.md update logic, and team pipeline routing table (currently only in team.md),
so that I am the single authoritative source for FSM pipeline behavior.

**Delivered by:** Conv 4

**Acceptance criteria:**
- AC1: `orchestrator.md` contains git commit instructions for the BUILDING → REVIEWING and REVIEWING → TESTING transitions.
- AC2: `orchestrator.md` contains the PROGRESS.md update logic (mark conv DONE, mark all Phase Detail rows DONE, set COMPLETE when all done).
- AC3: `orchestrator.md` contains a team pipeline routing table covering all FSM states to their sub-skills.
- AC4: `orchestrator.md` contains the artifact archiving dual-write rule.
- AC5: No content is duplicated between `team.md` (after conversion) and `orchestrator.md`.
