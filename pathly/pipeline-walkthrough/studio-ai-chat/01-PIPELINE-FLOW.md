---

---
# 01 — Pipeline Flow: studio-ai-chat

_Date: 2026-05-27 | Branch: shammai/chat_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "studio-ai-chat build fast"
│
│  [Stage 0 — Discovery]
│  (pre-pipeline — plan files already existed)
│
│  [Stage 1 — Planning]
│  (pre-pipeline — USER_STORIES.md, IMPLEMENTATION_PLAN.md,
│   CONVERSATION_PROMPTS.md, PROGRESS.md already written)
│
│  [Stage 2–3 — Build + Review]
│
├─► Conv 0 — Terminal dock + shells (S0.1–S0.3)
│   Builder → REVIEW_FAILURES.md (3 retries → HUMAN_QUESTIONS.md → human resolved)
│   Reviewer → PASS
│
├─► Conv 1 — FSM status endpoint + system prompt (S1.1–S1.2)
│   Builder → verify_gate FAILED → fixed inline
│   Reviewer → REVIEW_FAILURES.md (1 retry) → PASS
│
├─► Conv 2 — Conductor chat panel UI (S2.1–S2.4)
│   Builder → scope_gate FAILED (5×) → resolved via conv_start_sha update
│   Reviewer → PASS
│
├─► Conv 3 — MatchCard + terminal write (S3.1–S3.2)
│   Builder → clean
│   Reviewer → PASS
│
├─► Conv 4 — Context injection (S4.1–S4.2)
│   Builder → clean
│   Reviewer → REVIEW_FAILURES.md (2 retries) → PASS
│
├─► Conv 5 — Embedding router / MiniLM (S5.1–S5.3)
│   Builder → scope_gate FAILED (3×) → resolved
│   Reviewer → ARCH_FEEDBACK.md + REVIEW_FAILURES.md → both resolved → PASS
│
├─► Conv 6 — Static Studio schema (S6.1–S6.2)
│   Builder → scope_gate FAILED (1×) → resolved
│   Reviewer → REVIEW_FAILURES.md (1 retry) → PASS
│
├─► Conv 7 — Playwright executor + IPC (S7.1–S7.3)
│   Builder → scope_gate FAILED (1×) → resolved
│   Reviewer → REVIEW_FAILURES.md (1 retry) → PASS
│
├─► Conv 8 — Staged/auto automation mode (S8.1–S8.4)
│   Builder → scope_gate FAILED (1×) → resolved
│   Reviewer → REVIEW_FAILURES.md (1 retry) → PASS
│
├─► Conv 9 — Model selector + WebLLM (S9.1–S9.4)
│   Builder → clean (REVIEW.md artifact created manually)
│   Reviewer → PASS (require_artifact gate: REVIEW.md)
│
│  [Stage 4 — Test]
├─► Tester → TEST_FAILURES.md (S9.3: selectedModelId not wired)
│   Builder fix → getEngine(selectedModelId) added to ChatPanel/index.tsx
│   Tester re-run → PASS
│
│  [Stage 5 — Retro]
└─► Retro agent (quick)
    Writes: pathly/plans/studio-ai-chat/RETRO.md
            pipeline-walkthrough/studio-ai-chat/  ← this folder
```

---

## How agents communicate

Agents never call each other. The orchestrator is the only router.
Communication happens via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `CONSULT_architect.md` | Architect | Builder (deletes) | Pre-build findings to incorporate |
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `SCOPE_VIOLATION.md` | Gate | Orchestrator (manual conv_start_sha fix) | Diff exceeds declared scope |
| `TEST_FAILURES.md` | Tester | Builder (deletes) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline blocked on human decision |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| Conv 0 review | 3 | REVIEW_FAILURES.md retries → escalated | Human accepted item 1, fixed item 2 |
| Conv 1 review | 1 | REVIEW_FAILURES.md | Builder fix pass |
| Conv 2 build | 5 | scope_gate (tsconfig.tsbuildinfo + undeclared files) | conv_start_sha updated + CONVERSATION_PROMPTS.md file list patched |
| Conv 4 review | 2 | REVIEW_FAILURES.md | Builder fix pass |
| Conv 5 build | 3 | scope_gate | conv_start_sha + file paths fixed |
| Conv 5 review | 2 | ARCH_FEEDBACK.md + REVIEW_FAILURES.md | Architect redesign + builder fix |
| Conv 6–8 build | 1 each | scope_gate | conv_start_sha + file paths fixed |
| Conv 6–8 review | 1 each | REVIEW_FAILURES.md | Builder fix pass |
| Testing | 1 | S9.3: selectedModelId not wired to askWebLLM | Builder added getEngine(selectedModelId) call |

---

## FSM states traversed

```
BUILDING → REVIEWING → BUILDING (×10 conversations)
         → REVIEWING → TESTING → RETRO → DONE
```
