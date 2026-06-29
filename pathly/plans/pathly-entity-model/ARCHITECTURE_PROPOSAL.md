# Pathly Entity Model & Artifact Contract — ARCHITECTURE PROPOSAL

_Status: implementer-facing · drafted 2026-06-29 · synthesised from DESIGN.md + PO_NOTES.md; every file:line verified against the working tree._

This document is **self-contained**. An implementer reading only this file has everything
needed to begin Phase 0 without re-reading DESIGN.md. Source requirements:
`pathly/plans/pathly-entity-model/PO_NOTES.md` and `pathly/plans/pathly-entity-model/DESIGN.md`.

---

## 1. The core model — `scope` vs `slug`

> **`scope` answers "which board tier." `slug` answers "where on disk." They are different
> things. Today the code conflates them by passing `topic = scope` into the FSM. That
> conflation IS the production bug, and separating the two IS the structural fix.**

Two distinct identities, currently collapsed into one variable:

| Axis | `scope` | `slug` |
|---|---|---|
| Question it answers | which **board addressing tier** | where on **disk** the artifacts live |
| Values | `feature` → `<slug>` · `project` → `<abs path>` · `global` → `'global'` | a bare slug: `md-diagram-conversion`, `goal-fix-loop-3f9a1c22` |
| Used as | board-message `scope` column / context retrieval key | FSM `topic` → `pathly/<domain>/<slug>/` storage dir |

**Why a feature works today and a project goal does not:**

```
FEATURE (scope == slug, self-binding):
  scope = "md-diagram-conversion"  ── used as topic ──►
  Path(root) / "pathly" / "md-diagram-conversion"   ✓ resolves correctly

PROJECT GOAL (scope is an absolute path):
  scope = "C:/Users/Yafit/pathly-adapters"  ── used as topic ──►
  Path(root) / "pathly" / "C:/Users/Yafit/pathly-adapters"
       │
       └─► pathlib DISCARDS left operands when the right is absolute
           ⇒ collapses to the PROJECT ROOT itself
           ⇒ PO_NOTES gate checks <root>/PO_NOTES.md ── never matches ──►
              PO_DISCUSSING re-spawns the PO forever  ✗ THE BUG
```

The fix: **slug — not scope — becomes the FSM topic.** Project/global goals get a real slug
directory under `pathly/goals/<slug>/`; the FSM resolves storage there; the `PO_NOTES` gate
matches; the consultation FSM advances. The join key linking a board row to its folder is a
new nullable **`comms_messages.slug` column with a `UNIQUE` index** — never folder-equals-path.

### Taxonomy — 4 kinds; slug is identity, scope is addressing

| kind | folder | board row (`comms_messages`) | scope tier | FSM topic |
|---|---|---|---|---|
| **feature** | `pathly/plans/<slug>/` | folder + `STATE.json` | `feature`, scope=`<slug>` | `<slug>` (correct today) |
| **goal** (project) | `pathly/goals/<slug>/` | `type='goal'`, executor∈{single,loop,team} | `project`, scope=`<abs path>` | `<slug>` (was the abs path → bug) |
| **goal** (global) | `pathly/goals/<slug>/` | `type='goal'` | `global`, scope=`'global'` | `<slug>` |
| **lesson** | `pathly/lessons/` (flat) | `type='discovery'` (💡) | `global`/`project` | none (never runs an FSM) |
| **exploration** | `pathly/explorations/<slug>/` | `type='discovery'` | `feature`, scope=`<slug>` | `<slug>` |

### Recommended structure — keep `plans/`, add `goals/`

Do **NOT** rename `pathly/plans/` → `pathly/features/` (PO_NOTES Out-of-Scope #1; pure blast
radius, zero behavioral gain). The dual root is already live and backward-compatible.

```
pathly/
  plans/<slug>/              UNCHANGED — features. Full per-role artifact set
                             (STATE.json, EVENTS.jsonl, PO_NOTES.md, ARCHITECTURE_PROPOSAL.md,
                             RESEARCH.md, DESIGN.md, USER_STORIES.md, IMPLEMENTATION_PLAN.md,
                             CONVERSATION_PROMPTS.md, PROGRESS.md, FEATURE_INDEX.md, RETRO.md,
                             feedback/, + NEW ARTIFACTS.jsonl)
    .archive/                UNCHANGED
  goals/<goal-slug>/         NEW — project/global goals get a real slug dir. Today they have
                             NONE — that absence is the literal cause of the collapse bug.
                             Same artifact set; light mode writes DAG_PLAN.md.
  lessons/                   UNCHANGED — flat collection (LESSONS.md), NOT per-slug folders
  explorations/<slug>/       UNCHANGED
  debugs/<slug>/             UNCHANGED
  pipeline-walkthrough/      UNCHANGED
```

---

## 2. Layers touched — verified file:line inventory

All references below were verified against the working tree on 2026-06-29.

### Python — `src/pathly_orchestrator/`

| File | Site | What it is today | Change |
|---|---|---|---|
| `fsm_ops.py` | `:68-74` `_resolve_storage_path` | `Path(root)/"pathly"/topic` then template fallback — **the collapse** | Add `_safe_topic` guard at top; add `goals/<slug>` probe branch |
| `runner/argv.py` | `:13-21` `_storage_path` | single-template join — **CLI path only, NOT the goal collapse site** | Add `_safe_topic` guard for defense-in-depth (do not assume this alone fixes goals) |
| `supervisor/goal_decomposer.py` | `:113-135` `_decompose_planner` instructions; `:142` `skill=""` | hardcodes *"Do NOT create plan files"* and passes `skill=""` so no fragment reaches it | `skill="" → "planning/dag-sketch"`; delete the "Do NOT create plan files" line; write `DAG_PLAN.md` |
| `supervisor/goal_decomposer.py` | `:245-257` `_decompose_consultation` `_start(topic=scope)` | passes raw `scope` as `topic` | `topic=slug` (resolved via `ensure_goal_slug`) |
| `supervisor/goal_executor.py` | `:23-65` `_reset_fsm_state_for_flow` | `:52` forwards its `scope` arg straight into `_resolve_storage_path` | Pass a **slug** at the call sites; the reset then resolves correctly |
| `supervisor/goal_executor.py` | `:317` `_run_team` reset call **and** `:320-334` its `_start(topic=scope)` | BOTH pass raw scope | Both become slug. **Two callers** — the second is the audit's most-missed site |
| `supervisor/goal_executor.py` | `:223-231` `_run_loop` `RunnerState(topic=scope, …)` | loop executor seeds `topic=scope` | `topic=slug` |
| `supervisor/board_run.py` | `:246-255` `where_line` probe | gated on `board=='feature'` only; **no `slug` param** | Add `slug` param to `start_board_run`; extend probe to all tiers + `goals/<slug>/` branch |
| `supervisor/terminal.py` | `:39` `_write_supervisor_phase_summary`; `:269` `feature_dir`; `:307` `storage_path` | hardcoded `Path(root)/"pathly"/"plans"/topic` (×3) | **Thread the resolved `storage_path` from the caller** instead of reconstructing inline |
| `supervisor/terminal.py` | `:86` `_agent_done_watcher` | `project_root = feature_dir.parent.parent.parent` | **DO NOT CHANGE** — preserve as the depth invariant (see §5) |
| `supervisor/slug.py` | NEW file | — | `ensure_goal_slug(conn, goal_id)` under the write-lock |
| `supervisor/registry.py` | mirror write | writes STATE.json mirror | Make slug-aware |
| `db/queries/comms_artifacts.py` | NEW fn `ensure_attached` | attach/list/section CRUD exists | Add idempotent UPSERT keyed by `(scope, artifact_path)` + SSE `artifact_attached` |
| `db/migrations.py` | `comms_messages` schema | — | Add nullable `slug` column + UNIQUE index (additive) |
| `http_server/blueprints/fsm.py` | `/complete_stage` body | carries `flow`+`topic`+`project_root` | Thread optional `board`/`scope` (additive; absent → `board='feature', scope=topic`) |

### Skills / data — `src/pathly_data/core/skills/`

| File | Change |
|---|---|
| `composition.yaml` | NEW entry `planning/dag-sketch` with `artifact-register`. **Do NOT touch `defaults:` (`:24`)** — see §4 overspray decision. `planning/po` (`:119`) keeps its existing `comms-post`. Per-skill attach `artifact-register` only to pipeline-role skills with a manifest entry. |
| `artifact-manifest.yaml` | NEW — single source of truth for role→file→gate, read by BOTH composer and FSM gates |
| `fragments/artifact-register.md` | NEW fragment — write named artifact + append `ARTIFACTS.jsonl` line + advisory board POST |
| `planning/dag-sketch.md` | NEW skill body — agnostic: "decompose into 3-7 tasks; write `DAG_PLAN.md` with a `## Tasks` table; then post each task" |
| 4 adapter `_meta/` dirs | Sync via `pathly-setup claude --apply --repair` + `python -m build` |

### TypeScript — `studio/src/renderer/src/`

| File | Site | Change |
|---|---|---|
| `store/commsStore.ts` | `:140` `RESERVED = new Set(['plans', '.archive'])` | **Extend in Phase 1** to add `goals, lessons, explorations, debugs, pipeline-walkthrough` (one-line) |
| `store/commsStore.ts` | `:131-160` `loadFeatures` / `set({features})` | Phase 3: `loadFeatures → loadCards`; store `cards` slice with `features` as a derived `.filter(kind==='feature')` getter |
| `types.ts` | — | Phase 3: `CardKind = 'feature'\|'goal'\|'lesson'\|'exploration'`; `Card` superset; keep `Feature = Card & {kind:'feature'}` |
| `CardSidebar/` | replaces `FeatureSidebar` | Phase 3: grouped collapsible sections, behind a flag with `FeatureSidebar` fallback |

---

## 3. The 4-phase delivery plan

Each phase is independently shippable and backward-compatible with live features
(PO_NOTES Constraints). Adapter sync (`pathly-setup claude --apply --repair` + `python -m build`)
runs in any phase touching `core/`.

```
Phase 0  GUARD          ── ships in days, zero schema-behavior change
   │     _safe_topic (WARN) in _resolve_storage_path + argv._storage_path
   │     + nullable comms_messages.slug column + UNIQUE index (additive)
   ▼
Phase 1  BUG FIX        ── GATES Phase 2
   │     ensure_goal_slug · topic=slug at EVERY §2 site · goals/ probe
   │     · start_board_run slug param · thread storage_path into terminal.py
   │     · EXTEND Studio RESERVED set · flip _safe_topic to RAISE
   ▼
Phase 2  ARTIFACT       ── ATOMIC (core + 4 adapters in ONE commit)
   │     artifact-manifest.yaml + artifact-register.md + dag-sketch.md
   │     + composition.yaml entry + per-skill attachments + _decompose_planner edit
   │     + ensure_attached reconciler (complete_stage gate + post-PTY path)
   ▼
Phase 3  SIDEBAR        ── renderer-only
         loadFeatures→loadCards (cards/features-getter split) · CardSidebar behind flag
```

**Smallest first slice that delivers value:** Phase 0's `_safe_topic` guard — three lines,
no skill rebuild. Once flipped to RAISE in Phase 1 it immediately ends the project-goal
infinite loop, the most painful confirmed bug.

### Phase 0 — guard only (this week)
- `_safe_topic` in `_resolve_storage_path` (`fsm_ops.py:68`) + `argv._storage_path`, in **WARN
  mode** (log, don't raise) for one release to confirm no legitimate caller passes a path-like topic.
- Add nullable `comms_messages.slug` column + UNIQUE index (additive migration).
- _Tests: `test_fsm_ops.py` — feed an absolute Windows path AND a normal slug to `_resolve_storage_path`._

### Phase 1 — fix the bug + close the Studio regression window
- `supervisor/slug.py:ensure_goal_slug(conn, goal_id)` — under the write-lock (see §4).
- Route `topic=slug` at **every** site in §2: `_decompose_consultation`, **both** `_run_team`
  calls (reset + `_start`), the `_run_loop` executor, and `_reset_fsm_state_for_flow`.
- Extend `_resolve_storage_path` with the `goals/<slug>` probe branch.
- Add the `slug` param to `start_board_run`; extend the `where_line` probe to all tiers.
- Thread the resolved `storage_path` into the three `terminal.py` sites (`:39, :269, :307`).
- **Extend the Studio RESERVED set** (`commsStore.ts:140`) — cross-phase ordering fix below.
- Flip `_safe_topic` to **RAISE**.
- _Tests: drive **ONE REAL consultation decompose end-to-end** (mocks on both sides of the
  FSM↔driver boundary hide this exact class of bug — see MEMORY: FSM next_state contract bug);
  a concurrency test for `ensure_goal_slug`._

> **Cross-phase ordering fix (mandatory):** Phase 1 creates `pathly/goals/` on disk. Any Studio
> build whose RESERVED set is still `{plans, .archive}` will surface `goals` as a **phantom
> feature** in the sidebar. The RESERVED-set extension MUST ship in Phase 1, not Phase 3.

### Phase 2 — artifact contract (ATOMIC)

> **Atomic-commit constraint (PO_NOTES Constraints + DESIGN §3).** These MUST land in **ONE
> commit** — a partial deploy makes the planner call a non-existent skill and error:
> 1. `artifact-manifest.yaml`
> 2. `fragments/artifact-register.md`
> 3. `planning/dag-sketch.md`
> 4. its `composition.yaml` entry
> 5. per-skill `artifact-register` attachments (pipeline roles only)
> 6. the `_decompose_planner` edit (`skill="" → "planning/dag-sketch"`)
> 7. the 4-adapter sync output
>
> `validate_composition` MUST fail the build if `planning/dag-sketch` is referenced but absent —
> a build error, not a silent runtime no-op.

- Add `ensure_attached`; call from the `complete_stage` gate (thread `board`/`scope`) **and**
  the supervisor post-PTY path, with the JSONL-or-manifest-stat fallback (§4).
- FSM contract change is **additive only**: `agent_hint.instructions` gains the named artifact +
  `out_path`; `/complete_stage` gains optional `board`/`scope`; **`codex_subagent` stays frozen.**
- _Tests: regenerate `test_compose.py` snapshots in the same PR; new `test_artifact_reconcile.py`
  (JSONL path + manifest-stat fallback)._

### Phase 3 — Studio sidebar (renderer-only)
- `loadFeatures → loadCards` with the `cards` slice / `features`-getter split (avoids the
  store-shape bug where cards get erased on every `set({features})`).
- Ship `CardSidebar` behind a flag with `FeatureSidebar` fallback. Degrade to features-only if
  `/comms` is unreachable. Typecheck via `tsconfig.web.json`.
- Goal cards expose Decompose/Run (`/comms/goals/decompose` + `/comms/goals/run`); lesson click
  opens its `.md` in the MarkdownEditor.

---

## 4. Key architectural decisions (with rationale)

**D1 — `slug` UNIQUE index (not folder-equals-path).**
The join key is a new nullable `comms_messages.slug` column with a DB-level `UNIQUE` index.
`ensure_goal_slug` reuses `slug` if set, else `slugify(goal_text)[:48] + '-' + goal_id[:8]`,
persisted. It runs **inside the existing process-wide write-lock** (`_get_write_lock`,
reentrant) with a check-then-insert; the `UNIQUE` index is the DB-level backstop against a
racing double-insert across processes. `goal_id[:8]` = 32 bits ≈ 1-in-4-billion collision per
pair; the index catches even that. **Rationale:** durable identity that survives folder
moves/renames; never rely on a path string as a primary key.

**D2 — reconciler is the structural guarantee; the fragment is advisory.**
A fragment is prompt text — it cannot *guarantee* anything (PO_NOTES Out-of-Scope: board POST
must not be mandatory/blocking in the agent hot path; it violates the fragment doctrine). So we
build belt **and** suspenders:
- *Suspenders (the real guarantee):* a deterministic server-side reconciler. The FSM gate
  already `stat`s `storage_path/<artifact>` to decide whether to advance. Extend that exact
  stat: when the gate file first appears, `complete_stage` calls idempotent
  `comms_artifacts.ensure_attached(slug, board, scope, artifact_path, role)` — an UPSERT keyed
  by `(scope, artifact_path)` that creates the `comms_artifacts` row + emits SSE `artifact_attached`.
- *Non-FSM modes* (single-agent, light DAG via `start_board_run`, which never calls
  `complete_stage`): the supervisor post-PTY path reads `ARTIFACTS.jsonl` and calls the **same**
  `ensure_attached`. **Fallback** when the JSONL is absent (bootstrapping window or pre-fragment
  runs): look up the run's role in the manifest, `stat` `<storage_path>/<file>`, attach if present.
- *Belt (happy path):* `artifact-register.md` writes the named artifact to the injected
  `<out_path>` (never agent-chosen), appends one line to `ARTIFACTS.jsonl`
  `{role, path, type, title, summary, ts}` (mandatory, offline-proof), then does an advisory
  board POST (skip if down).

> **Two wiring gaps to close (both real, both small):** (1) `complete_stage` currently carries
> only `flow`+`topic`+`project_root` — thread `board`/`scope` (additive; absent → derive
> `board='feature', scope=topic`, correct for features today). (2) The reconciler MUST resolve
> paths through the **same slug-aware resolver** as the FSM (§5) — otherwise it silently no-ops
> for project goals, the entities that need it most.

**D3 — per-skill `artifact-register`, NOT `composition.yaml defaults:`.**
`defaults:` (currently `[progress-logging]`, `composition.yaml:24`) applies to **every** skill in
the `skills:` map — which would silently inject the register into `planning/po`,
`planning/evaluate`, `planning/consolidate`, etc. (overspray into non-pipeline skills). Instead
attach `artifact-register` **per-skill, only to pipeline-role skills** that have an
`artifact-manifest.yaml` entry. **The manifest's `roles:` map IS the allow-list.** `planning/po`
keeps its existing `comms-post` (it already writes `PO_NOTES.md`).

`artifact-manifest.yaml` shape (read by composer AND FSM gates so they can't drift):

```yaml
roles:
  po:             { file: PO_NOTES.md,                 gate: '#' }
  architect:      { file: ARCHITECTURE_PROPOSAL.md,    gate: '## ' }
  web-researcher: { file: RESEARCH.md,                 gate: '## ' }
  designer:       { file: DESIGN.md,                   gate: '## Design System Output' }
  planner:        { file: IMPLEMENTATION_PLAN.md,      gate: '## Phase' }
  reviewer:       { file: feedback/REVIEW_FAILURES.md, gate: '#' }
  tester:         { file: feedback/TEST_FAILURES.md,   gate: '#' }
  retro:          { file: RETRO.md,                    gate: '#' }
  explorer:       { file: CONCLUSIONS.md,              gate: '#' }
overrides:                       # keyed by (role, skill) when light mode differs
  planner.planning/dag-sketch: { file: DAG_PLAN.md, gate: '## Tasks' }
```

**D4 — RESERVED-set extension lands in Phase 1, not Phase 3.**
See the cross-phase ordering fix in §3. Phase 1 creates `pathly/goals/` on disk; without the
extension, `goals` surfaces as a phantom feature. One-line constant change. This is the single
most important sequencing rule across the whole plan.

**D5 — `_safe_topic` RAISE-immediately (after a one-release WARN soak).**
PO_NOTES Open Question #3, Phase 0/1 split: ship WARN in Phase 0 to confirm no legitimate caller
passes a path-like topic, then flip to RAISE in Phase 1. **The only runs hitting the guard are
already looping forever**, so RAISE turns a silent forever-loop into a loud escalate — strictly
better than the status quo. (Working assumption per PO_NOTES: RAISE immediately is acceptable;
the WARN soak is the conservative default chosen here to avoid breaking an unknown legitimate caller.)

**D6 — planner artifact parity in every mode.**
`_decompose_planner` (light path) is the only artifact-less decomposer today: it hardcodes
*"Do NOT create plan files"* and passes `skill=""`, so no fragment can ever reach it.
`_decompose_plan` (`skill="planning/plan"`) and `_decompose_consultation` already produce the
artifact set. Fix: light mode writes `DAG_PLAN.md` via `planning/dag-sketch`. Result ladder, all
artifact-bearing: light → `DAG_PLAN.md` · plan → full `IMPLEMENTATION_PLAN.md` set ·
consultation → full PO→…→planner set.

---

## 5. Critical implementation constraints

**C1 — Watcher depth invariant (the hardest rule).**
A storage path is **always exactly `pathly/<domain>/<slug>/`** — **two components under
`pathly`**. This keeps `_agent_done_watcher`'s
`project_root = feature_dir.parent.parent.parent` (`terminal.py:86`) correct.
`goals/<slug>/` is the same depth as `plans/<slug>/`, so the watcher is safe.

```
feature_dir = <root>/pathly/goals/<slug>
                          │      │      │
              .parent ────┘      │      │   → <root>/pathly/goals
              .parent ───────────┘      │   → <root>/pathly
              .parent ──────────────────┘   → <root>   ✓ project_root
```

A 3-component tree like `pathly/<kind>/<slug>/sub/` would break this computation. **Never add a
third path component under `pathly`.** This is exactly why kind-partitioning lessons into
per-slug folders is rejected.

**C2 — SOLID 400-line limit (Python) / ~150-line limit (TS components).**
PO_NOTES Constraints. Any touched file approaching the limit must be **split before** new code
is added. `goal_executor.py` (348 lines) and `board_run.py` (336 lines) are already near the
Python limit — adding the slug-threading there must be done with care; extract helpers into a
`_helpers.py` rather than growing the file. `CardSidebar/` follows the one-component-one-folder
rule (its own subfolder + `.module.css`).

**C3 — `_safe_topic` policy.**
The guard raises (Phase 1+) on: empty topic, absolute path, `.`/`..`, any `[\\/:]` separator, or
`..` in `Path(topic).parts`. Reference implementation:

```python
def _safe_topic(topic: str) -> str:
    if (not topic or os.path.isabs(topic) or topic in (".", "..")
            or re.search(r'[\\/:]', topic) or '..' in Path(topic).parts):
        raise ValueError(
            f"unsafe FSM topic {topic!r}: must be a bare slug, not a path/scope")
    return topic
```

Called at the **top of `_resolve_storage_path`** (`fsm_ops.py:68`) and in `argv._storage_path`.

**C4 — No `plans/ → features/` rename.**
PO_NOTES Out-of-Scope #1, DESIGN §1. ~14 prose/code sites for zero behavioral gain. The dual
root (`pathly/<slug>/` and `pathly/plans/<slug>/`) is already live; legacy `plans/` is the safe
default. Do not touch it.

**C5 — Adapter sync is mandatory for any `core/` change.**
`pathly-setup claude --apply --repair` + `python -m build`. A core skill/fragment change that
skips this leaves installed files stale; the changes never reach the running agent.

**C6 — Additive-only FSM contract.**
`/complete_stage` gains optional `board`/`scope` (absent → derive feature defaults).
`agent_hint.instructions` gains the named artifact + `out_path`. `codex_subagent` stays **frozen**.
No existing field changes meaning.

---

## 6. ARCH_QUESTIONs

**None blocking.** All four PO_NOTES Open Questions have working assumptions the design adopts,
and none require further product input before Phase 0 begins:

1. **Goal storage location** → decided: separate `pathly/goals/<slug>/` (sibling to `plans/`,
   same depth so the watcher is safe; makes sidebar grouping a pure function of the parent folder).
2. **Single-agent / taskless runs** → decided: **role optional**. If a role is set, the agent
   gets the artifact contract (named artifact + `ensure_attached` via the manifest); otherwise
   free-form board-post is fine. This is a Phase 2 detail and does not gate earlier phases.
3. **`_safe_topic` rollout** → decided: WARN in Phase 0 → RAISE in Phase 1 (D5).
4. **Lessons in sidebar** → decided: single "Lessons" collection node (keeps flat `LESSONS.md`);
   a Phase 3 rendering detail only.

If the implementer disagrees with **#2 (role-optional vs role-required)** during Phase 2, raise
it then — it is the only assumption with a defensible alternative, and it does not affect
Phases 0/1.

---

## Appendix — verified code sites (for the implementer)

- `src/pathly_orchestrator/fsm_ops.py:68-74` — `_resolve_storage_path` (the collapse; two-probe new-style→template). Guard + `goals/` branch go here.
- `src/pathly_orchestrator/supervisor/goal_decomposer.py:113-135` (`_decompose_planner` "Do NOT create plan files"), `:142` (`skill=""`), `:245-257` (`_decompose_consultation` → `_start(topic=scope)`).
- `src/pathly_orchestrator/supervisor/goal_executor.py:23-65` (`_reset_fsm_state_for_flow`, `:52` resolver call with raw scope), `:223-231` (`_run_loop` `RunnerState(topic=scope)`), `:317` (`_run_team` reset call), `:320-334` (`_run_team` `_start(topic=scope)`).
- `src/pathly_orchestrator/supervisor/board_run.py:246-255` — `where_line` probe gated on `board=='feature'`; `start_board_run` has no `slug` param today (signature at `:147`).
- `src/pathly_orchestrator/supervisor/terminal.py:39, 269, 307` — hardcoded `pathly/plans/<topic>` (×3); `:86` — `parent.parent.parent` watcher root (PRESERVE).
- `src/pathly_orchestrator/runner/argv.py:13-21` — single-template `_storage_path` (CLI path only; NOT the FSM/goal collapse site).
- `src/pathly_data/core/skills/composition.yaml:24` (`defaults: [progress-logging]`), `:119` (`planning/po` → `comms-post`), `:164` (`no_defaults` opt-out precedent).
- `studio/src/renderer/src/store/commsStore.ts:131-160` — `loadFeatures`; `:140` `RESERVED = new Set(['plans', '.archive'])`.
- Board taxonomy: `comms_messages.type ∈ {nudge, decision, question, answer, status, discovery, warning, escalation, task, artifact, goal, phase}`; scope tiers feature/project/global; `comms_artifacts` one row per file.

_Synthesised from DESIGN.md (5-lens design workflow: minimal-migration · clean-taxonomy ·
fragment-contract · commandcenter-ux · fsm-correctness) and PO_NOTES.md. Every file:line
re-verified against the working tree on 2026-06-29._
