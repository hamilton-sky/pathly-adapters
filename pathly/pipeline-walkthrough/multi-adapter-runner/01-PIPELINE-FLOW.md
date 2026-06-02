# 01 — Pipeline Flow: multi-adapter-runner

_Date: 2026-06-02 | Branch: master_

---

## Execution trace

```
User intent: "multi-adapter runner with pause/abort/caps and control API"
│
│  [Stage 1 — Planning]
│  (planned in prior session)
│
│  [Stage 2–3 — Build + Review]
│
├─► Builder Conv 1 — adapters.yaml + resolve_command + gen_adapters_ts  (45,219 tok · $0.24 · 281s)
│   └─► Reviewer Conv 1 — PASS (inline)
│
├─► Builder Conv 2 — RunnerState + supervisor loop + caps/abort  (61,954 tok · $0.33 · 436s)
│   └─► Reviewer Conv 2 — PASS (inline)
│
├─► Builder Conv 3 — HTTP control endpoints + SSE /events/runner  (61,176 tok · $0.33 · 220s)
│   └─► Reviewer Conv 3 — REVIEW_FAILED (3 violations)
│       └─► Builder fix:
│           - parse_result hardcoded "claude" → reads current_adapter
│           - /runner/start missing run_id in response → RunnerState.run_id UUID
│           - handle_decide() uses input() unconditionally → interactive=True param
│       └─► Reviewer Conv 3 round 2 — PASS  (48,337 tok · $0.26)
│           └─► STATE → TESTING
│
│  [Stage 4 — Test]
├─► Tester (analyze→scout→test)  (80,512 tok · $0.43)
│   └─► All 25 criteria PASS — STATE → RETRO
│
│  [Stage 5 — Retro]
└─► Retro agent → DONE
```

---

## How agents communicate

Agents never call each other. Communication via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes) | Stories not satisfied |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| Build Conv 1–2 | 0 | — | No violations |
| Build Conv 3 | 1 | 3 violations: hardcoded adapter, missing run_id, input() in headless path | Builder fix pass; round 2 passed |
| Test | 0 | — | All criteria satisfied first pass |

---

## FSM states traversed

```
PLANNING
  → REVIEWING (conv 1 built)
  → BUILDING  (conv 1 reviewed, more convs)
  → REVIEWING (conv 2 built)
  → BUILDING  (conv 2 reviewed, more convs)
  → REVIEWING (conv 3 built)
  → REVIEW_FAILED (3 violations found)
  → REVIEWING (violations fixed)
  → TESTING   (conv 3 reviewed clean)
  → RETRO     (all tests passed)
  → DONE
```
