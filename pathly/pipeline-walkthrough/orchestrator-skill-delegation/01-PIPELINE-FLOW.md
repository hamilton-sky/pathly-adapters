# 01 — Pipeline Flow: orchestrator-skill-delegation

_Date: 2026-05-14 | Branch: claude/frosty-rhodes-b98a74_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "not recorded"
│
│  [Stage 0 — Discovery]
│  Orchestrator → STORMING (auto-advance)
│
│  [Stage 1 — Planning]
│  (plan imported from existing plans/ folder — no planner agent spawned)
│
│  [Stage 2–3 — Build + Review]
│
│  Conv 2 — Shrink orchestrator to pure delegation
├─► Builder agent       tokens_in: 19,747 | tool_uses: 10 | wall: 56s  → DONE
├─► Reviewer agent      tokens_in: 13,388 | tool_uses:  3 | wall: 21s  → PASS
│
│  Conv 3 — Update flow YAMLs + fix debug bug
├─► Builder agent       tokens_in: 17,948 | tool_uses: 22 | wall: 131s → DONE
├─► Reviewer agent      tokens_in:  9,779 | tool_uses:  6 | wall: 17s  → PASS
│
│  [Stage 4 — Test]
│  (no tester spawned — verify was a git diff check)
│
│  [Stage 5 — Retro]
└─► Retro agent
    Writes: plans/orchestrator-skill-delegation/RETRO.md
            pathly/pipeline-walkthrough/orchestrator-skill-delegation/  ← this folder
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
| — | 0 | — | — |

---

## FSM states traversed

```
→ STORMING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ DONE
```
