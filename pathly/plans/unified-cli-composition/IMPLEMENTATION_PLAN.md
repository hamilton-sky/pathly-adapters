# Implementation Plan — unified-cli-composition (Gate 2)

_Scope: Gate 2 only. Gate 1 complete. Gate 3 deferred._

---

## Context

Gate 1 delivered: `POST /skills/compose`, `skillCompose.ts`, `compose.py`, `composition.yaml` (~20 skills), `client-file-output.md`, `artifact-transform.md`. Summary/Analyze/Split are on the composed path with file-based capture.

Gate 2 delivers: error normalization (pill surface), two new fragments (`board-start-context`, `task-dag-post`), the `planning/plan` manifest entry, Decompose conversion to `compose_skill()`, and the `build_adapter_caps()` drift-prevention helper.

Gate 3 (deferred): loop/drain board-I/O, `profiles:` rename.

---

## Phase 1 — Error normalization + new fragments + manifest entry

**Stories:** US-01, US-02, US-03, US-04

### Step 1.1 — Summary ActionPill error state (US-01)

**Files:**
- `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` (or ActionPill component — locate the Summary pill render path)
- `studio/src/renderer/src/services/skillCompose.ts` (error file polling logic)

**What:** The Summary action currently toasts on error but does not set ActionPill state to `error`. Extend the Summary result-read path to check for `ERROR:` prefix in the output file, then call the same `state='error'` setter that Analyze and Split already use.

**Done when:** US-01 acceptance criteria pass (pill turns error state, error text visible, no Analyze/Split regression).

### Step 1.2 — `board-start-context.md` fragment (US-02)

**Files:**
- `src/pathly_data/core/skills/fragments/board-start-context.md` (new)
- `src/pathly_data/core/skills/composition.yaml` (add capability gate entry)
- `src/pathly_orchestrator/skills/compose.py` (add `goal_id` to `_KNOWN_CAPABILITIES` and `adapter_caps_for()`)

**What:** Write the fragment. It must:
- Open with guard: skip silently when `goal_id` is absent.
- Instruct agent to call `GET /comms/retrieve?scope={scope}&goal_id={goal_id}&limit=10`.
- Mark the response as read-only context; no board mutation.
- Include "skip-if-down" advisory guard (board unreachable → emit "board context unavailable" and continue).

Extend `compose.py`: add `goal_id` to `_KNOWN_CAPABILITIES`, update `adapter_caps_for()` to propagate it, update `validate_composition()` if needed.

**Done when:** US-02 acceptance criteria pass — `POST /skills/compose` with/without `goal_id` produces correct prompt inclusion/exclusion.

### Step 1.3 — `task-dag-post.md` fragment (US-03)

**Files:**
- `src/pathly_data/core/skills/fragments/task-dag-post.md` (new)
- `src/pathly_data/core/skills/composition.yaml` (add capability gate entry referencing `goal_id`)

**What:** Write the fragment. It must:
- Instruct agent to use `POST /comms/post` with `type: "task"` (not `/comms/tasks` — see scout findings).
- Provide the full payload template: `title`, `description`, `goal_id`, `parent_id` (nullable), `depends_on` (array), `executor` (`single|loop|team`), `kind` (`"task"`).
- Be gated on `goal_id` presence (same capability as board-start-context).
- Follow established fragment structure patterns (H2 heading, curl bash template, skip-if-down guard).

**Done when:** US-03 acceptance criteria pass.

### Step 1.4 — `planning/plan` manifest entry (US-04)

**Files:**
- `src/pathly_data/core/skills/composition.yaml`

**What:** Extend the **existing** `planning/plan` skill entry (it already carries `completion-report`) — do NOT create a second `planning/plan` key. Add to its `fragments:` list:
- `board-start-context` (requires `goal_id`)
- `task-dag-post` (requires `goal_id`)

Use the existing `blocks:` key (no `profiles:` rename — Gate 3 only).

**Done when:** US-04 acceptance criteria pass — compose with/without `goal_id` produces correct fragment inclusion.

---

## Phase 2 — Decompose conversion

**Stories:** US-05, US-06, US-07, US-08

**Prerequisite:** Phase 1 complete. Both new fragments validated in isolation via manual `POST /skills/compose` calls before touching `goal_decomposer.py`.

### Step 2.1 — Side-by-side baseline capture (US-07 prerequisite)

**Files:** No code change.

**What:** Run a Decompose on a reference goal using the existing hard-coded path. Record: task count, task titles, dependency links, executor values. Capture as a reference fixture (inline comment or scratch notes) to compare against after conversion.

**Done when:** Baseline task DAG documented before any Python changes.

### Step 2.2 — Convert `_decompose_planner()` and `_decompose_plan()` (US-05, US-06, US-08)

**Files:**
- `src/pathly_orchestrator/supervisor/goal_decomposer.py`

**What:**
- Replace inline prompt string construction in `_decompose_planner()` with `compose_skill("planning/plan", adapter_caps, manifest)`.
- Replace inline prompt string construction in `_decompose_plan()` with the same call.
- Remove any stdout-parsing / `result.text` reference for the decompose result; read from `AGENT_DONE.summary` instead.
- Add `goal_id`, `executor`, `kind` to the `PHASE_START` event metadata.
- Do NOT touch `_decompose_consultation()`.

**Done when:** US-05, US-06, US-08 acceptance criteria pass.

### Step 2.3 — DAG equivalence verification (US-07)

**Files:** No code change.

**What:** Run the same reference goal through the new composition path. Compare the produced task DAG against the Phase 2.1 baseline. Document equivalence (or note any intentional improvements) in a code comment before removing the old path.

**Done when:** US-07 acceptance criteria pass — task count, titles, and dependencies are equivalent.

---

## Phase 3 — `build_adapter_caps()` helper and drift prevention

**Stories:** US-09, US-10 (US-10 verified)

### Step 3.1 — Extract `build_adapter_caps()` (US-09)

**Files:**
- `src/pathly_orchestrator/skills/compose.py` (add `build_adapter_caps(ctx)` function)
- `src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py` (replace inline adapter_caps dict with `build_adapter_caps()`)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (replace inline adapter_caps dict with `build_adapter_caps()`)

**What:**
- Define `build_adapter_caps(ctx: dict) -> dict` in `compose.py`. Returns at minimum: `can_spawn`, `goal_id`, `executor`, `kind`.
- Any future field added to adapter_caps belongs in this one function.
- Call sites that previously constructed adapter_caps inline now call `build_adapter_caps(ctx)`.

**Done when:** US-09 acceptance criteria pass — no inline `adapter_caps = {` dict construction at call sites; grep confirms.

### Step 3.2 — Final Gate 2 smoke test (US-10 verified)

**What:** Add a test fragment entry to `planning/plan` in `composition.yaml`, run compose, confirm the test fragment body is present in the output, remove the test entry. Confirms the whole chain works declaratively.

**Done when:** US-10 acceptance test passes.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Profile drift (HTTP vs supervisor paths compose different profiles) | `build_adapter_caps()` helper (Phase 3) closes this; reviewer checklist: any PR touching adapter_caps must use the helper |
| Decompose regression (task DAG differs from old path) | Baseline capture before conversion (Step 2.1); side-by-side verification (Step 2.3) before removing old code |
| Gate 3 scope creep (`blocks:` → `profiles:` rename) | Hard rule: no `blocks:` key rename in any Gate 2 PR; reviewer rejects on sight |
| `_decompose_consultation()` accidentally modified | Explicit "do not touch" note in Step 2.2; reviewer checks the diff is scoped to `_planner` and `_plan` only |
| Error normalization skipped | Phase 1 Step 1.1 is a prerequisite for all subsequent phases; do not start Phase 2 until US-01 passes |

---

## Acceptance: Gate 2 done when

All ten stories' acceptance criteria pass, plus:
1. `compose_skill("planning/plan")` is the only prompt source for Decompose (no inline Python prompt string).
2. `AGENT_DONE.summary` is the only result-capture mechanism for Decompose.
3. `goal_id`, `executor`, `kind` in every `PHASE_START` event for Decompose runs.
4. `build_adapter_caps()` is the only place adapter_caps dicts are constructed.
5. No `blocks:` → `profiles:` rename anywhere in the diff.
