# Board Evaluation — context-retrieval-quality

## Classification
BOTH

## Summary
The board carries a concrete, well-grounded PROPOSAL with three retrieval-quality issues (ISSUE-1, ISSUE-2, ISSUE-4) mapped to exact code paths in `comms_context.py` and the skill/fragment layer. The task DAG has been updated (2026-07-01): all three tasks now carry `context_refs` pointing at the PROPOSAL, CT3 has `depends_on: [CT1]` so the claim-time fallback can't run before CT1's per-tier gate ships, and CT3's text calls out the 3-part decomposition required before coding starts. Code targets verified against the current codebase — all still accurate.

## Key unknown / risk
CT3's claim-time fallback (`tasks.py:99-125`) reuses CT1's `_SEMANTIC_MAX_DISTANCE` dict. This dependency is now enforced in the DAG. No remaining merge-conflict risk if the dependency order is respected.

## Gaps resolved (2026-07-01)

### GAP-1 — CT3 missing `depends_on: [CT1]` ✅ FIXED
CT3 now has `depends_on: ["38a731d2-8435-450e-94f2-eda77b395c05"]` (CT1). The old task (`a9dca1dd`) was soft-deleted and superseded. The scheduler can no longer pick CT3 before CT1 completes.

### GAP-2 — CT3 is a 3-part task; the PROPOSAL calls it "its own DAG" ✅ DOCUMENTED
CT3's updated text now explicitly notes the required decomposition before coding:
- T3a: `planning/dag-sketch.md` + `fragments/task-dag-post.md` (enforce at decompose)
- T3b: `tasks.py:99-125` + `comms_context.py` (claim-time fallback, depends T3a+CT1)
- T3c: new coverage route (depends T3b)
A builder claiming CT3 is now instructed to decompose first.

### GAP-3 — All tasks had `context_refs: null` ✅ FIXED
All three tasks (CT1, CT2, CT3) now have `context_refs: [{"artifact": "pathly/features/context-retrieval-quality/PROPOSAL.md"}]`. Agents claiming any task will get 📎 Referenced context (the PROPOSAL) rather than falling back to the noisier 💡 semantic channel.

## Remaining gap

### GAP-4 — Goal has no executor
**Severity:** Low (runner path only)  
**Status:** Not patched — the HTTP API doesn't expose a goal-executor update endpoint; direct DB access would be needed. For headless runs, pass `executor_override: "single"` to `POST /comms/goals/run`. Interactive board runs are unaffected.

## What IS correct (verified 2026-07-01)

- **CT1 code target:** `comms_context.py:22` — `_SEMANTIC_MAX_DISTANCE = 0.75` (still single float, CT1 converts it to a per-tier dict). Loop guard at `:148`.
- **CT2 code targets:** score surfacing at `:255` (`entry = f"  • {text}  [{header}]"` — no score shown yet); elbow gating at `:148-154` (single threshold, no gap check yet). Both in the same loop CT1 modifies.
- **CT2 → CT1 dependency:** correct. `1 - dist` score to surface is the same loop CT1 modifies; sequential in one PR is right.
- **CT3 independent of CT2:** score-surfacing doesn't affect CT3's decompose-time enforcement or claim-time fallback. CT3 depends only on CT1.
- **dag-sketch.md and task-dag-post.md exist:** `src/pathly_data/core/skills/planning/dag-sketch.md` and `src/pathly_data/core/skills/fragments/task-dag-post.md` — CT3/T3a targets confirmed real files.
- **Claim route is the right T3b insertion point:** `tasks.py:99-125` (`comms_tasks_claim`) — after `claim_task` succeeds, check `context_refs` on the claimed row and auto-derive if empty.

## Active task DAG (post-fix)

```
CT1 [38a731d2] — per-tier distance gate  ←  no depends, READY to claim
  └─ CT2 [7906e630] — scores + elbow gating  ←  depends CT1
  └─ CT3 [83349497] — context_refs enforcement  ←  depends CT1, decompose before coding
```

## Recommended next steps

- Claim CT1 first — one file (`comms_context.py`), two-line change + regression test
- CT2 ships in the same PR as CT1 (same file, same function)
- When CT3 is claimed: decompose into T3a → T3b → T3c before implementation
- GAP-4: add `executor: "single"` to the goal when/if headless execution is needed
