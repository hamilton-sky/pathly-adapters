# agent-architecture-refactor — Implementation Plan

---

## Conversation 1: Scout-pattern migration   ← Conversation: 1

**Stories:** S1.1, S1.2

### Phase 1 — Replace scout-path call in build.md and review.md

**File:** `src/pathly_data/core/skills/build.md`
**File:** `src/pathly_data/core/skills/review.md`
Replace each `Call \`scout-path\`` instruction with a `Spawn **scout** agent` inline delegation block, following the pattern in `src/pathly_data/core/skills/team/review.md`.
**Done when:** `grep "scout-path" src/pathly_data/core/skills/build.md src/pathly_data/core/skills/review.md` returns no invocation lines.

---

### Phase 2 — Replace scout-path call in test.md

**File:** `src/pathly_data/core/skills/test.md`
Replace `call **scout-path**` (~line 66) with a `Spawn **scout** agent` inline delegation block.
**Done when:** `grep "scout-path" src/pathly_data/core/skills/test.md` returns no invocation line.

---

### Phase 3 — Replace scout-path calls in team/build.md and team/test.md

**File:** `src/pathly_data/core/skills/team/build.md`
**File:** `src/pathly_data/core/skills/team/test.md`
Replace each `Call \`scout-path\`` instruction with a `Spawn **scout** agent` inline delegation block.
**Done when:** `grep "scout-path" src/pathly_data/core/skills/team/build.md src/pathly_data/core/skills/team/test.md` returns no invocation lines.

---

### Phase 4 — Update explore.md (two lines)

**File:** `src/pathly_data/core/skills/explore.md`
- Line ~83: replace `call **scout-path**` with `Spawn **scout** agent`
- Line ~166: replace `Explorer + scout-path only` with `Explorer + scout agent only`
**Done when:** `grep "scout-path" src/pathly_data/core/skills/explore.md` returns no results.

---

### Phase 5 — Add standalone-only note to scout-path.md

**File:** `src/pathly_data/core/skills/scout-path.md`
Add a note after the opening callout: scout-path is for standalone invocation only; pipeline stages spawn the scout agent directly.
**Done when:** `scout-path.md` contains both "standalone" and "pipeline" in the new note.

---

### Phase 6 — Update team/discover.md subagents table

**File:** `src/pathly_data/core/skills/team/discover.md`
Update the subagents table entry that references scout-path to describe the direct spawn pattern.
**Done when:** The subagents table in `team/discover.md` no longer references `scout-path` as the mechanism.

---

### Phase 6.5 — Replace scout-path calls in team/plan.md with parallel scout spawns

**File:** `src/pathly_data/core/skills/team/plan.md`

This file was missing from the original Conv 1 scope. It contains two scout-path call sites (Storm Phase 2 and Plan Phase 2) and references them in the subagents table.

**Changes:**

1. **Subagents table** (top of file): replace `scout-path (ROLE: architect)` and `scout-path (ROLE: planner)` with `scout agent — parallel per entry (architect lens)` and `scout agent — parallel per entry (planner lens)`.

2. **Storm Phase 2 — Research**: replace `Call scout-path with: NEEDS_CONTEXT block from Phase 1, ROLE: architect` with a parallel scout spawn block:
   - **Default: always parallel.** Spawn one scout agent per NEEDS_CONTEXT entry simultaneously — up to 4 scouts at once (matching the NEEDS_CONTEXT cap of 4 entries). Scope overlap is not a problem — scouts are read-only and each has its own question.
   - **Sequential only** when entry B's question references entry A's answer (e.g. "that class", "the above", "what you found"). In that case, wait for A to complete before spawning B.
   - Collect all findings. Synthesize into a single Research Findings block before Phase 3.

3. **Plan Phase 2 — Scout**: same replacement with planner lens instead of architect lens.

**Done when:**
- `grep "scout-path" src/pathly_data/core/skills/team/plan.md` returns no invocation lines.
- `grep "parallel" src/pathly_data/core/skills/team/plan.md` returns the parallel spawn instruction in both Phase 2 blocks.

---

## Conversation 2: Worker agent contracts + YAML   ← Conversation: 2

**Stories:** S2.1, S2.2, S2.3, S2.4, S2.5

### Phase 7 — Add scout spawn section to tester.md

**File:** `src/pathly_data/core/agents/tester.md`
Add a subagent delegation section after the existing `## Phase: analyze` block. Structure must match builder.md and reviewer.md. Include `type: scout` (multi-file test infrastructure investigation) and `type: quick` (single-file lookups). Include `way of thinking` and `constraints` fields.
**Done when:** `tester.md` contains a scout delegation section with `way of thinking` and `constraints` fields.

---

### Phase 8 — Upgrade builder.md delegation pattern

**File:** `src/pathly_data/core/agents/builder.md`
In the existing scout delegation block, add `way of thinking` (implementation patterns, utility functions, naming conventions, import paths) and `constraints` (read only, do not suggest fixes, stay within stated scope) fields — matching the structure already in reviewer.md and architect.md.
**Done when:** `builder.md` scout delegation block contains both `way of thinking` and `constraints` fields.

---

### Phase 9 — Add scout spawn section to planner.md

**File:** `src/pathly_data/core/agents/planner.md`
Add a scout delegation section. Remove the line "Planner does not spawn scouts — codebase investigation is builder's domain." Add `type: scout` for cross-file architecture investigation and `type: quick` for single-file lookups. `way of thinking`: understand current architecture, existing patterns, integration points, and delivered scope — do not make HOW decisions. `constraints`: read only, do not suggest implementation approaches.
**Done when:** `planner.md` contains a scout delegation section and no longer contains the "Planner does not spawn scouts" line.

---

### Phase 10 — Update claude/tester.yaml can_spawn

**File:** `src/pathly_data/adapters/claude/_meta/tester.yaml`
Change `can_spawn: [builder]` → `can_spawn: [quick, scout, builder]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/claude/_meta/tester.yaml` returns `can_spawn: [quick, scout, builder]`.

---

### Phase 11 — Update codex/tester.yaml can_spawn

**File:** `src/pathly_data/adapters/codex/_meta/tester.yaml`
Change `can_spawn: [builder]` → `can_spawn: [quick, scout, builder]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/codex/_meta/tester.yaml` returns `can_spawn: [quick, scout, builder]`.

---

### Phase 12 — Update claude/planner.yaml can_spawn

**File:** `src/pathly_data/adapters/claude/_meta/planner.yaml`
Change `can_spawn: [quick, web-researcher]` → `can_spawn: [quick, scout, web-researcher]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/claude/_meta/planner.yaml` returns `can_spawn: [quick, scout, web-researcher]`.

---

### Phase 13 — Update codex/planner.yaml can_spawn

**File:** `src/pathly_data/adapters/codex/_meta/planner.yaml`
Change `can_spawn: [quick, web-researcher]` → `can_spawn: [quick, scout, web-researcher]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/codex/_meta/planner.yaml` returns `can_spawn: [quick, scout, web-researcher]`.

---

## Conversation 3: Explorer agent parity   ← Conversation: 3

**Stories:** S3.1, S3.2

### Phase 14 — Add scout spawn section to explorer.md and remove no-spawn hard rule

**File:** `src/pathly_data/core/agents/explorer.md`
Remove the line "Do NOT spawn additional agents." Add a scout delegation section consistent with builder.md/reviewer.md structure. `way of thinking`: look for code paths, dependencies, structural patterns relevant to the exploration question. `constraints`: scouts are terminal and read-only — explorer remains read-only on production code.
**Done when:** `explorer.md` contains a scout delegation section and no longer contains "Do NOT spawn additional agents".

---

### Phase 15 — Update claude/explorer.yaml can_spawn

**File:** `src/pathly_data/adapters/claude/_meta/explorer.yaml`
Add `can_spawn: [scout, quick]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/claude/_meta/explorer.yaml` returns `can_spawn: [scout, quick]`.

---

### Phase 16 — Update codex/explorer.yaml can_spawn

**File:** `src/pathly_data/adapters/codex/_meta/explorer.yaml`
Add `can_spawn: [scout, quick]`.
**Done when:** `grep "can_spawn" src/pathly_data/adapters/codex/_meta/explorer.yaml` returns `can_spawn: [scout, quick]`.

---

## Conversation 4: Orchestrator conversion   ← Conversation: 4

**Stories:** S4.1, S4.2

### Phase 17 — Add missing FSM sections to orchestrator.md

**File:** `src/pathly_data/core/agents/orchestrator.md`
Add four sections (sourced from team.md), placed before "## What you must NOT do":
1. Git commit instructions for BUILDING → REVIEWING and REVIEWING → TESTING transitions
2. PROGRESS.md update logic (mark conv DONE, mark Phase Detail rows DONE, set COMPLETE)
3. Team pipeline routing table (IDLE/STORMING → team/discover, PLANNING → team/plan, BUILDING → team/build, REVIEWING → team/review, TESTING → team/test, RETRO → team/retro, BLOCKED_ON_HUMAN → wait + restore, DONE → stop)
4. Artifact archiving dual-write rule
**Done when:** `grep -c "dual-write\|routing table\|PROGRESS.md\|git commit" src/pathly_data/core/agents/orchestrator.md` returns 4 or more matches.

---

### Phase 18 — Convert team.md to thin launcher

**File:** `src/pathly_data/core/skills/team.md`
**Keep:** argument parsing, feature detection, mode selection, nano mode (all five nano steps).
**Remove:** FSM operations, state recovery, entry stage override, routing table, orchestrator responsibilities between stages, artifact archiving rule.
**Add:** a `## Spawn orchestrator` section (between mode selection and nano mode) that spawns the orchestrator agent with FEATURE, rigor, autoFlow, and entryStage.
**Done when:**
- `grep "FSM operations\|State recovery\|routing table" src/pathly_data/core/skills/team.md` returns no results.
- `grep "orchestrator" src/pathly_data/core/skills/team.md` returns the spawn instruction line.

---

## Cross-cutting constraints

- No file outside each conversation's scope may be modified.
- `planner.md` and `po.md` changes in Conv 2 are the only intentional agent contract changes — `po.md` is not modified (PO already has web-researcher spawning; scout/quick remain intentionally excluded).
- `team/review.md` must not be changed — it is the reference pattern.
- Each conversation must leave the repository in a consistent state (no half-replaced files).
- Verify command after each conversation: `git diff --stat` showing only the listed files.
