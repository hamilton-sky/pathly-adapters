# PROPOSAL — context-retrieval quality

_Branch: `shammai/context-retrieval-quality`. Surfaced by dogfooding storage-restructure Phase 2
through the board — see the system evaluation on the `storage-restructure-p2` board._

---

## A. Session status — achieved & remaining

### ✅ Achieved

1. **Board-scope fix-list** — all 12 review findings + the goal-completion-watcher correctness gate
   (arm the board-lock poll only for board-lock-backed paths; consultation/team would false-complete).
   `EvalConfigPopover` split into `BoardEvalConfig` + `GoalTargetConfig` (+ `useEvaluateBoardButton`
   hook); consultation confirm gate; target-lock; per-tier `BoardSelect` disable. `tsc 0`.
   → checkpoint `f49bdc3f`, pushed.
2. **Storage-restructure Phase 2 (safe slice)** — `_goal_storage_dir` nests feature-tier goals at
   `pathly/features/<feature>/goals/<slug>` (planner/plan decompose); `_project_root_from_storage`
   fixes the `parent.parent.parent` landmine (latent since Phase-1); Studio discovery scans
   `pathly/features/*` so the sidebar reflects the layout. 9 tests. → `c53a9aae`, merged to
   `shammai/board-design` (ff) + pushed.
3. **Dogfooded Pathly to build Phase 2** — created a feature board + goal + 5-task DAG + artifacts via
   `/comms`; audited the injected context; **walked the DAG frontier** (complete→unblock, incl. the
   multi-dep gate); posted the evaluation to the board; feature home links directory ↔ sidebar ↔ DB board.
4. **System analysis** — strong core (board substrate, DAG scheduler, governance cascade, B1 fix,
   read-only context preview); weak link = semantic retrieval; surfaced + fixed a real FSM landmine.
5. **This proposal** — concrete, code-grounded solutions for every open issue (below). → `36fc08c3`.

### ⏳ Remaining (this workstream)

- **Retrieval fixes** — implement §B: ISSUE-1 (per-tier gate) + ISSUE-2 (scores + elbow) as the first
  PR; ISSUE-4 (context_refs enforcement + claim-time fallback) as its own DAG.
- **Storage Phase 2 tail** — consultation FSM nesting (needs feature-threading through
  `_resolve_storage_path` + the fsm_compose root fix already landed); T3 project/global scope homes;
  resolver `features/<feature>/goals/<slug>` candidate.
- **Storage Phase 3** — Studio-discovery migration of existing folders + delete the legacy probe
  (discovery half started: `loadFeatures` already scans `features/`).
- **Commit hygiene** — the board-scope / file-claims A/B split (coupled via the `files` column +
  migration; deferred to master-PR time, re-split with interactive rebase).

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

---

## D. Production-readiness assessment (whole-system)

_Method: 4 parallel scouts (reliability · testing · security · scale-ops). The scale-ops scout
completed; the other three stalled on an environment watchdog, so those dimensions are synthesized
from this session's direct analysis + the code. Evidence cited inline._

**Verdict: solid engineering core; usable internally, NOT yet ready for untrusted or multi-tenant
production.** The FSM/board/DAG/DB-concurrency foundation is well-built and unusually well-tested for
its age. The gaps are concentrated in **security posture** (agent execution + board injection),
**operational hardening** (crash recovery, multi-project correctness, operator observability), and
**frontend test coverage**.

### 1. Reliability & correctness — strong core, recovery gaps
- **Strengths:** DB-authoritative FSM state + `STATE.json` mirror + deterministic `orchestrator` recovery; `board_lock` serialises runners; real integration tests (`test_runner_fsm_integration`, `test_runner_contract`, `test_two_flows`); the historic FSM contract / split-brain / `convs_done` bugs are fixed **and** regression-tested.
- **Risks:** **P1** `board_lock` is in-memory (`board_lock.py`) → an FSM crash mid-run loses the lock; a restart can spawn a *duplicate* runner on the same board → corrupted task DAG. · **P2** corrupt-state recovery depends on an LLM agent (non-deterministic in the recovery path).
- **Gaps:** persist/recover the board-lock on startup (scan `runner_state`); idempotent stage completion; a deterministic (non-LLM) state-recovery fallback.

### 2. Testing & quality gates — a STRENGTH (Python), thin on frontend
- **Strengths:** **90+ Python test files** across every layer + `e2e_install`; real FSM integration tests; **CI exists** (`.github/workflows/{test,e2e,lint,publish,studio-ci,studio-release}` + dependabot); version-sync check.
- **Risks:** **P1** the Electron/React control surface is **typecheck-only** — no runtime/unit/e2e tests for the Command Center, board interactions, or IPC. · **P2** no coverage measurement / threshold gate.
- **Gaps:** frontend runtime tests (Vitest + Playwright for the board + IPC); coverage reporting in CI.

### 3. Security & safety — the biggest production blocker
- **Strengths / mitigations:** FSM server **binds 127.0.0.1 by design** ([middleware.py:93](../../../src/pathly_orchestrator/http_server/middleware.py#L93)); `codex` adapter runs `--sandbox workspace-write`; argv dash-safety.
- **Risks:** **P0** agents execute with **`--dangerously-skip-permissions`** (`argv.py` / `terminal.ts` / `adapters.yaml`) — full shell/FS access, no sandbox on the claude path. · **P0** **prompt-injection → code execution**: board content (`comms_messages`) is injected into every prompt (`comms_context.py`) and agents then run code; **`/comms/*` has no authz**, so any local writer can influence what an agent executes. Skip-permissions + injectable board = an RCE vector. · **P1** no authz on `/comms/*` or `/runner/*` — localhost binding is the *only* control.
- **Gaps:** sandbox the claude execution (container/workspace jail); authenticate + authorize board posts and runner control; treat board content as **untrusted** in prompts (provenance labels + injection defenses); ensure the "human adjudicates" gate covers anything an agent will execute.

### 4. Scale & operations — solid concurrency, thin operability _(scale-ops scout)_
- **Strengths:** SQLite WAL + `busy_timeout` + process-wide write-lock (no lock cascade); dual-cap spawn scheduler + rate-limit backoff; `project_root` scoping; cost/billing telemetry resilient to failure.
- **Risks:** **P0** WAL-checkpoint vs write-lock contention under many concurrent agents → writer stalls / tail latency (`connection.py:130-150`). · **P1** multi-project **cost mis-patching**: the stop hook finds "most recent AGENT_DONE" project-agnostically → two Studio windows race → wrong feature billed (`stop_telemetry.py:23-38`). · **P1** scheduler + FSM metrics live only in the Electron console → headless operators have no diagnostics. · **P2** additive-only migrations (no rollback); unbounded `fsm_events`/`comms_messages` growth (no retention/vacuum).
- **Gaps:** checkpoint timeout + duration metrics; project-scoped cost patching; export scheduler/FSM metrics to a telemetry endpoint; migration versioning + rollback; DB retention/backup story; documented load limits.

### Path to production (prioritized)

| Tier | Item |
|---|---|
| **P0** | Sandbox claude agent execution · authz on `/comms` + `/runner` · treat board content as untrusted (injection defenses) · WAL-checkpoint contention fix |
| **P1** | Persist/recover board-lock · project-scoped cost patching · frontend runtime tests · export scheduler/FSM metrics |
| **P2** | Migration versioning + rollback · DB retention/backup · coverage gates · deterministic state-recovery fallback · documented load limits |

The **retrieval-quality fixes in §B** are independent of this list and can ship first as a quick quality win. Related prior context: `pathly/.research/PRODUCTION_READINESS_FINDINGS.md` and the 2026-06-28 readiness assessment (`pathly/plans/readiness-assessment-2026-06/`).
