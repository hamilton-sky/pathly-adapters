# PROPOSAL — context-retrieval quality

_Branch: `shammai/context-retrieval-quality`. Surfaced by dogfooding storage-restructure Phase 2
through the board — see the system evaluation on the `storage-restructure-p2` board._

The board substrate + DAG scheduler are sound. The **semantic context channel** is the weak link:
it admits tangential cross-tier items and hides match confidence. These proposals target the exact
code paths in `runner/comms_context.py` + `db/queries/comms_embeddings.py`.

| # | Issue | Root cause | Proposed fix | Risk |
|---|---|---|---|---|
| 1 | Semantic channel leaks cross-board | project/global tiers each contribute fixed top-k; one loose global distance gate | **per-tier distance gate** | Low |
| 2 | Low query sensitivity on small boards | small corpus → fetch≈all → same top-k; confidence invisible | **surface scores + elbow gating** | Low |
| 4 | 📎 referenced tier empty w/o context_refs | refs only wired by decompose; hand/loose tasks get none | **enforce at decompose + claim-time fallback** | Med |
| 3 | (fixed) project_root landmine | `parent.parent.parent` fixed-depth | done in Phase 2 (`_project_root_from_storage`) | — |

---

## ISSUE-1 — semantic channel leaks cross-board low-relevance items

**Root cause.** `retrieve_board_context` ([comms_context.py:127-154](../../../src/pathly_orchestrator/runner/comms_context.py#L127)) loops the enabled boards with fixed slot counts — feature `k=3`, project `k=2`, global `k=1` — and applies ONE global relevance gate `_SEMANTIC_MAX_DISTANCE = 0.75` ([:22](../../../src/pathly_orchestrator/runner/comms_context.py#L22)). Scope filtering is correct (`search_by_embedding` keys on `board IN (…) AND scope IN (…)`), so this is not a leak bug — the project board's 2 slots simply always fill with *its* closest items, and 0.75 is too permissive to reject cross-domain matches (a storage task pulled two "Board differ" project notes at distance < 0.75).

**Proposed fix — per-tier distance gate.** The agent's OWN board is presumed relevant; cross-tier boards must clear a stricter bar:
```python
# comms_context.py
_SEMANTIC_MAX_DISTANCE = {"feature": 0.75, "project": 0.55, "global": 0.50}
# in the per-board loop, gate on the tier's own threshold:
cutoff = _SEMANTIC_MAX_DISTANCE[board_type]
if dist is not None and dist > cutoff:
    continue
```
Cross-tier items now appear only when genuinely close, while same-board recall is unchanged.

**Variant (adaptive).** Admit a project/global match only if `dist <= best_feature_dist + Δ` (relative to the best same-board match) — self-tuning, no magic per-tier constants. Recommend shipping the per-tier gate first (simple, safe), consider the adaptive variant if tuning proves fiddly.

---

## ISSUE-2 — low query sensitivity on small boards + invisible confidence

**Root cause.** `fetch_k = k + over_fetch_margin` ([:128](../../../src/pathly_orchestrator/runner/comms_context.py#L128)) over-fetches; on a small board that's ~all messages, so after the gate + `k` cap the same top-k return regardless of query nuance. Worse, the rendered 💡 lines ([:242-263](../../../src/pathly_orchestrator/runner/comms_context.py#L242)) show **no similarity score**, so a reader can't tell "5 strong matches" from "5 = everything on the board."

**Proposed fix (two parts).**
1. **Surface the score** in each 💡 line so confidence is legible (and the `/preview` audit becomes trustworthy):
   `• <text>  [architect → *, 11h · sim 0.42]`  (sim = `1 - _distance`, omitted for keyword/recency hits).
2. **Elbow gating** — stop padding at a large distance jump instead of always filling `k`:
   ```python
   if kept and dist is not None and prev_dist is not None and dist - prev_dist > _ELBOW_GAP:
       break   # weak tail past the relevance cliff — don't pad to k
   ```
   On a small/narrow board this yields *fewer, honest* matches rather than k-padded noise.

**Why not just lower k?** k is fine when the board is rich; the problem is padding *weak* matches. Elbow gating adapts to the actual distance distribution; score-surfacing makes whatever remains self-describing.

---

## ISSUE-4 — 📎 referenced tier empty without `context_refs`

**Root cause.** The authoritative 📎 channel ([comms_context.py:156-159](../../../src/pathly_orchestrator/runner/comms_context.py#L156)) hydrates only a task's `context_refs`, which are wired by the planner/`dag-sketch` skill during decompose. Tasks created by a lighter path (or by hand) carry none → the agent falls back to the noisier 💡 semantic channel. Context quality silently depends on the decompose step.

**Proposed fix (source + safety net).**
1. **Enforce at source.** Add a post-decompose validator: a DAG whose tasks lack `context_refs` fails a lint (or emits a board `warning`). Bake the "every task carries ≥1 ref" contract into the `planning/dag-sketch` skill + `fragments/task-dag-post`.
2. **Claim-time fallback.** When a claimed task has no `context_refs`, auto-derive them: run the board-artifact semantic search, promote the top-N *strong* hits (reuse ISSUE-1's per-tier gate) into implicit refs so they hydrate into 📎 instead of leaking through 💡. Closes the gap regardless of who created the task.

**Observability.** Surface a per-goal "refs coverage" count on the board (tasks-with-refs / total) so the gap is visible to the human before a run.

---

## Recommended sequencing

1. **ISSUE-1 per-tier gate** + **ISSUE-2 score-surfacing** — one small PR to `comms_context.py`, immediately improves every prompt + the `/preview` audit. Add a regression test asserting a below-threshold cross-tier item is dropped.
2. **ISSUE-2 elbow gating** — same file, guarded by a constant; test the small-board case.
3. **ISSUE-4** — larger: skill/fragment contract + claim-time fallback + coverage metric. Its own DAG.

All are additive and default-safe (thresholds/among existing channels); none change the board schema.
