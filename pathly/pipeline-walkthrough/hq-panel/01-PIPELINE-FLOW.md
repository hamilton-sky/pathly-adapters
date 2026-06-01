# 01 — Pipeline Flow: hq-panel

_Date: 2026-06-01 | Branch: master_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "HQ Panel — visual pipeline control for multi-adapter runner"
│
│  [Stage 0 — Discovery]
│  Orchestrator → PLANNING (auto-advance)
│
│  [Stage 1 — Planning]
├─► Planner agent
│   Produces:
│     pathly/plans/hq-panel/USER_STORIES.md
│     pathly/plans/hq-panel/IMPLEMENTATION_PLAN.md
│     pathly/plans/hq-panel/CONVERSATION_PROMPTS.md
│     pathly/plans/hq-panel/PROGRESS.md
│
│  [Stage 2-3 — Build + Review]
│
├─► Builder agent — Conv 1 (Phases 0–3: rename, runnerStore, FlowControlBar, StageStatusStrip)
│   tokens_in: 51,254  tokens_out: 12,814  cost: $0.346  tools: 52  wall: 765s
│   Produces: HQ/ folder, runnerStore.ts, FlowControlBar/, StageStatusStrip/
│   │
│   └─► Reviewer (inline) — Round 1: 9 violations
│         REVIEW_FAILURES.md written → artifacts/REVIEW_FAILURES_conv2_attempt1_resolved.md
│         Violations: inline styles (CSS var), button logic (retryEnabled), missing subtitle
│
├─► Builder agent — Conv 1 fix cycle
│   Resolves REVIEW_FAILURES.md → deleted after fixes
│   Reviewer re-run — Round 2: PASS
│
├─► Builder agent — Conv 2 (Phases 4–6: SSE client, decision menu, live cost/session)
│   tokens_in: 31,888  tokens_out: 7,972  cost: $0.215  tools: 26  wall: 153s
│   Produces: useHQ.tsx (SSE), PathlyMenuCard (decision mode), StageStatusStrip (live wiring)
│   │
│   └─► Reviewer (inline) — PASS (no new failures)
│
│  [FSM gate — REVIEWING → TESTING]
│  GATE_FAILED: require_artifact — REVIEW.md missing from plan folder
│   └─► HUMAN_QUESTIONS.md written
│         Resolved manually → FEEDBACK_RESOLVED
│         STATE_TRANSITION: REVIEWING → TESTING (2026-06-01T16:13:56Z)
│
│  [Stage 4 — Test]
├─► Tester (inline — no spawn event)
│   19 acceptance criteria evaluated
│   Round 1: 5 failures (TEST_FAILURES.md) → artifacts/TEST_FAILURES_conv1_attempt1.md
│   │
│   └─► Builder agent — test fix cycle (conv=0)
│         tokens_in: 30,636  tokens_out: 7,659  cost: $0.207  tools: 21  wall: 141s
│         Fixes: retryEnabled logic, optimistic clear, CSS var via ref, subtitle DOM element
│         TEST_FAILURES.md deleted
│
├─► Tester re-run (inline)
│   19/19 PASS — no TEST_FAILURES.md written
│
│  [Stage 5 — Retro]
└─► Retro agent
    Writes: pathly/plans/hq-panel/RETRO.md
            pipeline-walkthrough/hq-panel/  ← this folder
```

---

## How agents communicate

Agents never call each other. The orchestrator is the only router.
Communication happens via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `CONSULT_architect.md` | Architect | Builder (deletes) | Pre-build findings to incorporate |
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline blocked on human decision |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| Review (Conv 1) | 1 | 9 CLAUDE.md violations: inline CSS vars, wrong button logic, missing subtitle | Builder fixed all 9; reviewer re-run passed |
| Gate REVIEWING→TESTING | 1 | REVIEW.md artifact missing (reviewer didn't write it) | HUMAN_QUESTIONS.md created, resolved manually |
| Test | 1 | 5 criteria failed: retryEnabled wrong state, no optimistic clear, inline style, subtitle | Builder fixed all 5; tester re-run 19/19 PASS |

---

## FSM states traversed

```
→ REVIEWING   (conv 1 builder done — 2026-06-01T14:48:21Z)
→ REVIEWING   (conv 2 builder done — 2026-06-01T14:57:51Z)
  GATE_FAILED (require_artifact — 2026-06-01T16:13:23Z)
  FEEDBACK_RESOLVED (HUMAN_QUESTIONS.md — 2026-06-01T16:13:56Z)
→ TESTING     (2026-06-01T16:13:56Z)
→ RETRO       (test pass — all 19 ACs green)
→ DONE
```
