# Conversation Prompts — unified-cli-composition (Gate 2)

_Each conversation leaves the codebase in a runnable state._
_Prerequisite: Gate 1 is complete (compose seam, client-file-output, artifact-transform, Summary/Analyze/Split converted)._

---

## Conversation 1 — Error normalization + new fragments + manifest entry

**Stories delivered:** US-01, US-02, US-03, US-04

**This conversation must be complete before Conversation 2 starts.**

---

You are implementing Gate 2 of the unified-cli-composition feature for the Pathly project. Gate 1 is already shipped. Your job in this conversation is to deliver four things in order: Summary error pill, the `board-start-context` fragment, the `task-dag-post` fragment, and the `planning/plan` manifest entry.

### Context

- Gate 1 shipped: `POST /skills/compose`, `skillCompose.ts`, `compose.py`, `composition.yaml`, `client-file-output.md`, `artifact-transform.md`. Summary/Analyze/Split are on the composed + file-based-capture path.
- Fragment capability gating: `compose.py` has `_KNOWN_CAPABILITIES` (currently only `can_spawn`). Adding `goal_id` gating requires: add to `_KNOWN_CAPABILITIES`, update `adapter_caps_for()`, and update `validate_composition()` if needed.
- Task creation API: agents use `POST /comms/post` with `type: "task"` in the body — NOT `POST /comms/tasks`.
- Fragment structure patterns: open with H2 heading, show exact endpoint URLs with curl bash templates, include "Server availability — skip-if-down (advisory)" guard section, use `{ name: fragment-name, requires: capability-flag }` in composition.yaml.

### Phase 1 — Summary ActionPill error state (US-01)

The Summary action currently toasts on error but does not set ActionPill state to `error`. Analyze and Split already set pill state to `error` correctly (implemented in `useEditorAgentActions.ts` polling logic).

**Files to touch:**
- `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` — find the Summary result-read path; extend it to check for `ERROR:` prefix in the output file, then call the same `state='error'` setter used by Analyze/Split.
- `studio/src/renderer/src/services/skillCompose.ts` if the error polling hook lives there.

**Done when:** Manually trigger a Summary run where the agent writes `ERROR: test-error-message` to the output file; the pill renders an error state with that text. Analyze and Split error states are unaffected.

### Phase 2 — `board-start-context.md` fragment (US-02)

**Files to create/touch:**
- `src/pathly_data/core/skills/fragments/board-start-context.md` (new) — pull-once-at-start board context preamble.
- `src/pathly_orchestrator/skills/compose.py` — add `goal_id` to `_KNOWN_CAPABILITIES`; update `adapter_caps_for()` to include `goal_id` from context.

**Fragment must:**
- Open with a guard: if `goal_id` is absent, skip the entire fragment (agent sees nothing from it).
- Instruct the agent to call `GET /comms/retrieve?scope={scope}&goal_id={goal_id}&limit=10`.
- Mark the response as read-only preamble — no board mutation allowed from this fragment.
- Include a skip-if-down advisory: if the board is unreachable, emit "board context unavailable" and continue.

**Done when:** `POST /skills/compose` with `goal_id` present returns a prompt containing the `GET /comms/retrieve` instruction. Same call without `goal_id` returns a prompt without it.

### Phase 3 — `task-dag-post.md` fragment (US-03)

**Files to create:**
- `src/pathly_data/core/skills/fragments/task-dag-post.md` (new)

**Fragment must:**
- Instruct the agent to use `POST /comms/post` with `type: "task"` (not `/comms/tasks`).
- Provide the full payload template with all required fields:
  - `title` (string)
  - `description` (string)
  - `goal_id` (from spawn context — not optional)
  - `parent_id` (nullable)
  - `depends_on` (array of task IDs)
  - `executor` (`single|loop|team`)
  - `kind` (`"task"`)
- Be gated on `goal_id` presence (same `requires: goal_id` capability gate as board-start-context).
- Follow established fragment structure: H2 heading, curl bash template, skip-if-down guard.

**Done when:** `POST /skills/compose` with `goal_id` returns a prompt containing a `POST /comms/post` curl template with `type: "task"`. Same call without `goal_id` does not include it.

### Phase 4 — `planning/plan` manifest entry (US-04)

**Files to touch:**
- `src/pathly_data/core/skills/composition.yaml`

**What:** The `planning/plan` entry **already exists** in `composition.yaml` (it currently carries `completion-report`). Extend that existing entry — do NOT add a second `planning/plan` key. Use the existing `blocks:` key (no `profiles:` rename — Gate 3 only). Add to its `fragments:` list:
- `board-start-context` with `requires: goal_id`
- `task-dag-post` with `requires: goal_id`

**Done when:** `compose_skill("planning/plan", caps_with_goal_id, manifest)` returns a string containing both new fragment bodies. `compose_skill("planning/plan", caps_without_goal_id, manifest)` returns the skill body without either new fragment (the existing `completion-report` and the `progress-logging` default remain present).

---

## Conversation 2 — Decompose conversion

**Stories delivered:** US-05, US-06, US-07, US-08

**Blocked on:** Conversation 1 complete AND both new fragments validated in isolation via manual `POST /skills/compose` calls.

---

You are implementing the Decompose conversion for the unified-cli-composition Gate 2 feature. Conversation 1 is complete: `board-start-context.md`, `task-dag-post.md`, and the `planning/plan` manifest entry are live and validated. Your job is to convert `_decompose_planner()` and `_decompose_plan()` in `goal_decomposer.py` to use `compose_skill()`.

### Context

- `goal_decomposer.py` is at `src/pathly_orchestrator/supervisor/goal_decomposer.py`.
- Target functions: `_decompose_planner()` and `_decompose_plan()` only. Do NOT touch `_decompose_consultation()`.
- Current state: these functions build a prompt string inline in Python and parse the CLI result from stdout.
- Target state: call `compose_skill("planning/plan", adapter_caps, manifest)` to get the prompt; result captured from `AGENT_DONE.summary` in EVENTS.jsonl, not stdout.
- `AGENT_DONE.summary` is the authoritative result channel — this is how all other goal-backed runs work today.

### Phase 1 — Baseline capture (US-07 prerequisite, no code change)

Before modifying any Python, run a Decompose on a reference goal using the current code. Record:
- Task count
- Task titles (or representative sample)
- Dependency links
- Executor values

Document this baseline as a code comment in `goal_decomposer.py` before converting the function. This comment is the comparison baseline for Phase 3.

### Phase 2 — Convert `_decompose_planner()` and `_decompose_plan()` (US-05, US-06, US-08)

**Files to touch:**
- `src/pathly_orchestrator/supervisor/goal_decomposer.py`

**Changes:**
1. Import `compose_skill` (or the appropriate path) at the top of the file (or inside the function body — follow existing import patterns in the file to avoid circular imports).
2. Replace the inline prompt string in `_decompose_planner()` with `compose_skill("planning/plan", adapter_caps, manifest)`.
3. Replace the inline prompt string in `_decompose_plan()` with the same call.
4. Remove stdout-tail / `result.text` parsing for the decompose result. Read from `AGENT_DONE.summary` via EVENTS.jsonl.
5. Add `goal_id`, `executor`, `kind` to the `PHASE_START` event metadata dict.

**Do not touch `_decompose_consultation()`.**

**Done when:**
- US-05: neither function contains an inline prompt string for planning/plan.
- US-06: result is read from `AGENT_DONE.summary`; no stdout parsing.
- US-08: `PHASE_START` event contains `goal_id`, `executor`, `kind`.

### Phase 3 — DAG equivalence verification (US-07)

Run the same reference goal through the new composition path. Compare the produced task DAG against the Phase 1 baseline:
- Task count matches.
- Titles are equivalent in intent.
- Dependency links are preserved.
- No tasks duplicated or dropped.

Document the comparison result as a comment before removing the old inline code path.

**Done when:** Equivalence confirmed and documented. Old inline prompt string removed.

---

## Conversation 3 — `build_adapter_caps()` helper and Gate 2 smoke test

**Stories delivered:** US-09, US-10 (verified)

**Blocked on:** Conversation 2 complete.

---

You are closing out Gate 2 of unified-cli-composition. Conversations 1 and 2 are complete. Your job is to extract `build_adapter_caps()` to prevent future profile drift, then run the final Gate 2 smoke test.

### Context

- Two paths call `compose_skill()`: the HTTP path (`editor_render.py` → `POST /skills/compose`) and the supervisor path (`goal_decomposer.py` → in-process `compose_skill()`).
- If both paths construct `adapter_caps` inline, they can silently diverge when a new context field is added.
- The fix: a single `build_adapter_caps(ctx)` function in `compose.py` called by both paths.

### Phase 1 — Extract `build_adapter_caps()` (US-09)

**Files to touch:**
- `src/pathly_orchestrator/skills/compose.py` — add `build_adapter_caps(ctx: dict) -> dict`. Must return at minimum: `can_spawn`, `goal_id`, `executor`, `kind`. Any future field added to adapter_caps belongs here.
- `src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py` — replace inline adapter_caps dict construction with a call to `build_adapter_caps(ctx)`.
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` — replace inline adapter_caps dict construction with a call to `build_adapter_caps(ctx)`.

**Done when:** `grep -r "adapter_caps = {" src/pathly_orchestrator/` returns no results (all construction goes through the helper).

### Phase 2 — Gate 2 smoke test (US-10 verified)

1. Add a temporary test fragment entry to the `planning/plan` entry in `composition.yaml`.
2. Call `POST /skills/compose` with `goal_id` present.
3. Confirm the test fragment body appears in the composed prompt.
4. Remove the test fragment entry.
5. Confirm the test fragment body is gone from the composed prompt.

**Done when:** The declarative round-trip works. US-10 verified.

### Phase 3 — Update PROGRESS.md

Mark all three conversations as DONE in `pathly/plans/unified-cli-composition/PROGRESS.md`. Gate 2 is complete.
