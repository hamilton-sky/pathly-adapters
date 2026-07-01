# User Stories — unified-cli-composition (Gate 2)

_Scope: Gate 2 only. Gate 1 is complete. Gate 3 is deferred._
_Audience: Pathly engineering maintainer and Studio users relying on Summary/Analyze/Split/Decompose._

---

## US-01 — Summary error surfaces in ActionPill (not just toast)

**As** a Studio user running a Summary action,
**I want** an `ERROR:` output from the CLI engine to appear as an error state on the Summary ActionPill,
**So that** I can see at a glance that the summary failed without hunting through toasts that may have dismissed.

**Acceptance criteria:**
- When the CLI engine writes a file whose content begins with `ERROR:`, the renderer reads that file and sets the ActionPill state to `error`.
- The error message text from the file appears inside the pill (not only in a toast).
- No regression: Analyze and Split already render errors in their ActionPill; those states still work.
- Verified by: manually trigger a Summary run where the agent writes `ERROR: test-error-message` to the output file; confirm the pill turns red with the error text.

**Delivered by:** Conversation 1, Phase 1.

---

## US-02 — `board-start-context` fragment injects board preamble for goal-backed skills

**As** a Pathly engineering maintainer,
**I want** a `board-start-context` fragment that instructs the agent to fetch board context once at the start when a `goal_id` is present,
**So that** goal-backed agent runs begin with governance, active tasks, and recent decisions already in context — without any Python-side construction of that context block.

**Acceptance criteria:**
- The fragment file `core/skills/fragments/board-start-context.md` exists.
- When `compose_skill()` is called with `goal_id` present in adapter_caps, the composed prompt includes the board-start-context section.
- When `compose_skill()` is called without `goal_id`, the fragment is absent from the composed prompt (no empty section, no error).
- The fragment instructs the agent to call `GET /comms/retrieve?scope={scope}&goal_id={goal_id}&limit=10`.
- The fragment instructs the agent to treat the response as read-only preamble — no board mutation from this fragment.
- If the board is unreachable, the agent emits "board context unavailable" and continues; it does not abort.
- Verified by: `POST /skills/compose` with `goal_id` present returns a prompt containing the `GET /comms/retrieve` instruction; the same call without `goal_id` returns a prompt that does not.

**Delivered by:** Conversation 1, Phase 2.

---

## US-03 — `task-dag-post` fragment instructs structured task-tree writes

**As** a Pathly engineering maintainer,
**I want** a `task-dag-post` fragment that gives the agent a precise instruction for posting task records to the board,
**So that** the agent's task-tree output lands on the board with correct structure (title, description, goal_id, parent_id, depends_on, executor, kind) without Python code at the call site constructing the payload.

**Acceptance criteria:**
- The fragment file `core/skills/fragments/task-dag-post.md` exists.
- The fragment specifies `POST /comms/post` with `type: "task"` as the API call (not `/comms/tasks`).
- The fragment is only composed when `goal_id` is present in adapter_caps; absent `goal_id` → fragment is skipped.
- The fragment's payload template includes all required fields: `title`, `description`, `goal_id`, `parent_id` (nullable), `depends_on` (array), `executor` (`single|loop|team`), `kind` (`"task"`).
- Verified by: `POST /skills/compose` with `goal_id` returns a prompt containing a `POST /comms/post` instruction with `type: "task"`; the same call without `goal_id` does not include it.

**Delivered by:** Conversation 1, Phase 3.

---

## US-04 — `planning/plan` manifest entry composes both Gate 2 fragments

**As** a Pathly engineering maintainer,
**I want** the existing `planning/plan` entry in `composition.yaml` extended to include `board-start-context` and `task-dag-post` (alongside its existing `completion-report`),
**So that** a single manifest edit controls the full fragment profile for Decompose — no code change needed to add or remove a fragment from the Decompose skill.

**Acceptance criteria:**
- The existing `planning/plan` entry in `composition.yaml` is extended (not duplicated) — exactly one `planning/plan` key exists.
- That entry lists `board-start-context` (gated on `goal_id`) and `task-dag-post` (gated on `goal_id`) alongside its existing `completion-report` fragment.
- The `blocks:` key is used (no `profiles:` rename — that is Gate 3).
- Verified by: `compose_skill("planning/plan", caps_with_goal_id, manifest)` returns a string that includes both new fragment bodies; `compose_skill("planning/plan", caps_without_goal_id, manifest)` returns the skill body without either new fragment (the existing `completion-report` remains).

**Delivered by:** Conversation 1, Phase 4.

---

## US-05 — Decompose uses `compose_skill` instead of a hand-coded Python prompt

**As** a Pathly engineering maintainer,
**I want** the Decompose path in `goal_decomposer.py` to call `compose_skill("planning/plan", ...)` instead of building a prompt string in Python,
**So that** I can change the Decompose prompt profile by editing `composition.yaml` rather than editing Python at five separate call sites.

**Acceptance criteria:**
- `_decompose_planner()` and `_decompose_plan()` in `goal_decomposer.py` both call `compose_skill("planning/plan", ...)` to obtain their prompt.
- Neither function contains an inline prompt string for the planning/plan skill body.
- `_decompose_consultation()` is not touched.
- Verified by: run a goal Decompose end-to-end; inspect the spawn event — the prompt contains the `planning/plan` skill body as composed (not a hand-written string).

**Delivered by:** Conversation 2, Phase 1.

---

## US-06 — Decompose result captured via `AGENT_DONE.summary`, not stdout parsing

**As** a Pathly engineering maintainer,
**I want** the Decompose supervisor to read its result from `AGENT_DONE.summary` in EVENTS.jsonl rather than parsing CLI stdout,
**So that** the Decompose result is never truncated by PTY buffer limits and is identical regardless of which CLI engine (claude or codex) ran the agent.

**Acceptance criteria:**
- After a Decompose run, the supervisor reads the task list from `AGENT_DONE.summary`; no `result.text` / stdout-tail parsing occurs at the supervisor.
- The EVENTS.jsonl for the feature contains an `AGENT_DONE` event with a non-empty `summary` field after a successful Decompose.
- Verified by: run a goal Decompose; confirm `EVENTS.jsonl` contains `AGENT_DONE` with `summary`; confirm the supervisor does not call any stdout-parsing helper.

**Delivered by:** Conversation 2, Phase 1.

---

## US-07 — Produced task DAG is equivalent to the old hard-coded path

**As** a Studio user triggering goal Decompose,
**I want** the tasks posted to the board to be structurally identical to those the old hard-coded path produced,
**So that** switching to the composition path does not silently regress the task DAG quality or structure.

**Acceptance criteria:**
- Run a Decompose on a reference goal using the old path; record the resulting task DAG (task count, titles, dependencies).
- Run the same goal through the new composition path; the task count matches, titles are equivalent in intent, dependency links are preserved.
- No tasks are duplicated or dropped.
- Verified by: side-by-side comparison documented in a comment or test fixture before the old path is removed.

**Delivered by:** Conversation 2, Phase 2.

---

## US-08 — `goal_id`, `executor`, and `kind` appear in PHASE_START for every Decompose run

**As** a Pathly engineering maintainer debugging a Decompose run,
**I want** `goal_id`, `executor`, and `kind` logged in the `PHASE_START` event,
**So that** I can tell exactly which spawn profile was selected for any given run without reading source code.

**Acceptance criteria:**
- After a Decompose run, EVENTS.jsonl contains a `PHASE_START` event with `goal_id`, `executor`, and `kind` as metadata keys.
- When `goal_id` is absent (standalone compose call), the `PHASE_START` event contains `goal_id: null`.
- Verified by: inspect EVENTS.jsonl after a Decompose run for the three keys.

**Delivered by:** Conversation 2, Phase 1.

---

## US-09 — `build_adapter_caps()` helper prevents profile drift between HTTP and supervisor paths

**As** a Pathly engineering maintainer,
**I want** a single `build_adapter_caps(ctx)` helper in `compose.py` used by both the HTTP (`editor_render.py`) path and the supervisor (`goal_decomposer.py`) path,
**So that** both paths always compose the same fragment profile for the same spawn context — no silent divergence.

**Acceptance criteria:**
- A `build_adapter_caps(ctx)` function exists in `compose.py`.
- `editor_render.py` calls `build_adapter_caps()` to construct adapter_caps (not an inline dict).
- `goal_decomposer.py` calls `build_adapter_caps()` to construct adapter_caps (not an inline dict).
- `build_adapter_caps()` returns a dict containing at minimum: `can_spawn`, `goal_id`, `executor`, `kind`.
- Verified by: grep for inline `adapter_caps = {` constructions at call sites — none should exist after this story is done.

**Delivered by:** Conversation 2, Phase 3.

---

## US-10 — Developer can add a fragment to Decompose by editing only `composition.yaml`

**As** a Pathly engineering maintainer,
**I want** to add a new fragment to the Decompose skill profile by editing only `composition.yaml`,
**So that** prompt engineering changes to Decompose are isolated to the manifest and do not require touching Python or TypeScript.

**Acceptance criteria:**
- Add a new fragment name to the `planning/plan` entry in `composition.yaml`.
- The next Decompose run includes that fragment in the composed prompt with zero Python changes.
- Removing the entry restores the original prompt.
- Verified by: add a test fragment entry, run compose, inspect composed prompt for the test fragment body.

**Delivered by:** Implicitly proven by US-04 + US-05. No additional implementation work; the acceptance test is the final verification run.
