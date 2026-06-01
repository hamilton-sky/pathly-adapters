# 01 — Pipeline Flow: multi-adapter-routing

_Date: 2026-06-01 | Branch: master_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "not recorded"
│
│  [Stage 0 — Discovery]
│  (not recorded — plan files pre-existed)
│
│  [Stage 1 — Planning]
│  (plan files pre-existed at feature start)
│
│  [Stage 2–3 — Build + Review]
│
├─► Conv 1 | builder → DONE (wall: 379s)
│   FSM: → REVIEWING
├─► Conv 1 | (no reviewer recorded — conv 1 went directly to conv 2)
│
├─► Conv 2 | builder → DONE (wall: 185s)
│   FSM: → REVIEWING
├─► Conv 2 | reviewer → PASS (wall: 206s, 109578 tokens, $0.59)
│   Gate: GATE_FAILED require_artifact (REVIEWING→TESTING blocked)
│   Human: FEEDBACK_RESOLVED — HUMAN_QUESTIONS.md
│   FSM: REVIEWING → TESTING
│   FSM: → BUILDING (conv 3 start)
│
├─► Conv 3 | builder → DONE (wall: 844s)
│   FSM: → REVIEWING
├─► Conv 3 | reviewer → PASS (wall: 100s, 27289 tokens, $0.15)
│   Human: HUMAN_RESPONSE "continue"
│   FSM: REVIEWING → TESTING
│   FSM: → BUILDING (conv 4 start)
│
├─► Conv 4 | builder → DONE (wall: 780s)
│   FSM: → REVIEWING
├─► Conv 4 | reviewer → PASS (wall: 199s, 20371 tokens, $0.11)
│   Human: HUMAN_RESPONSE "auto-advance"
│   FSM: REVIEWING → TESTING
│   FSM: IMPLEMENT_COMPLETE
│
│  [Stage 4 — Test]
└─► Conv 0 | tester → PASS (wall: 594s, 31643 tokens, $0.17)
    FSM: TESTING → RETRO
```

---

## How agents communicate

Agents never call each other. The orchestrator is the only router.
Communication happens via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline blocked on human decision |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| REVIEWING→TESTING | 1 | GATE_FAILED require_artifact after Conv 2 review | Human resolved HUMAN_QUESTIONS.md manually |

---

## FSM states traversed

```
REVIEWING (conv 1 → reviewer gate)
REVIEWING (conv 2 → reviewer PASS)
  GATE_FAILED: require_artifact
  FEEDBACK_RESOLVED: HUMAN_QUESTIONS.md
TESTING (unblocked)
BUILDING (conv 3)
REVIEWING (conv 3 → reviewer PASS)
TESTING
BUILDING (conv 4)
REVIEWING (conv 4 → reviewer PASS)
TESTING → IMPLEMENT_COMPLETE
RETRO
DONE
```
