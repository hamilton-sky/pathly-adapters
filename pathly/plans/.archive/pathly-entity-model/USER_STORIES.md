# User Stories — pathly-entity-model

_Last updated: 2026-06-29_
_Source: PO_NOTES.md + ARCHITECTURE_PROPOSAL.md_

---

## Phase 0 — Guard

### S0.1 — Path-safe FSM topic (guard)

**Who:** Any Pathly developer running board-driven workflows.
**What:** When the FSM receives a topic that is an absolute path, an empty string, or contains
path separators, it raises `ValueError` immediately with a clear message, rather than silently
corrupting the storage path.
**Why:** The current silent collision (pathlib discards left operands for absolute paths) turns
a mis-wired call site into an infinite PO loop with no error signal.

Delivered by: Phase 0, Conversation 0.

**Acceptance criteria:**
- `_safe_topic("")` raises `ValueError`.
- `_safe_topic("C:/Users/Yafit/pathly-adapters")` raises `ValueError`.
- `_safe_topic("my-feature-slug")` returns `"my-feature-slug"` unchanged.
- `_safe_topic("..")` raises `ValueError`.
- `_safe_topic("a/b")` raises `ValueError`.
- `pytest tests/test_fsm_ops.py` passes with all five cases covered.
- `runner/argv._storage_path` calls `_safe_topic` for defense-in-depth.

### S0.2 — Slug column in comms_messages

**Who:** Platform engineers and the database.
**What:** `comms_messages` gains a nullable `slug` TEXT column with a UNIQUE index. Existing rows
are unaffected. The migration is idempotent (re-running it does not error).
**Why:** The slug column is the durable join key between a board message and its filesystem folder.
Without it there is no way to recover the slug for a goal that was created before Phase 1.

Delivered by: Phase 0, Conversation 0.

**Acceptance criteria:**
- `comms_messages` has a `slug` column after migration.
- A UNIQUE index exists on `comms_messages.slug` (verified via `PRAGMA index_list`).
- Inserting a duplicate slug raises an integrity error.
- Inserting a row with `slug=NULL` succeeds (nullable).
- The migration is re-runnable without error (idempotent `ALTER TABLE` pattern).

---

## Phase 1 — Bug Fix

### S1.1 — Project goal consultation advances past PO_DISCUSSING

**Who:** A platform engineer or product owner running a project-level goal decomposition via the
Command Center.
**What:** When a project goal is decomposed via consultation mode, the FSM advances through
`PO_DISCUSSING` and completes — it does not loop forever.
**Why:** This is the confirmed production bug. Project-goal scope is an absolute path; passing it
as the FSM topic collapses the storage path to the project root; the PO_NOTES gate never matches.

Delivered by: Phase 1, Conversation 1.

**Acceptance criteria:**
- A project goal with `scope = "<abs project path>"` is decomposed via consultation mode.
- The FSM advances past `PO_DISCUSSING` within one PO round-trip.
- `pathly/goals/<slug>/PO_NOTES.md` exists after the run (not `<abs path>/PO_NOTES.md`).
- No `ValueError` from `_safe_topic` (the slug is clean before reaching the guard).
- Verified via one real end-to-end run (not mocked FSM transitions — see MEMORY lesson on
  FSM next_state contract bug).

### S1.2 — ensure_goal_slug produces a stable, unique slug

**Who:** The supervisor calling `ensure_goal_slug(conn, goal_id)`.
**What:** The function returns the same slug on every call for a given `goal_id`, even when called
concurrently from multiple processes.
**Why:** The slug must be stable so the storage folder is always the same and board messages
can be joined to artifacts reliably.

Delivered by: Phase 1, Conversation 1.

**Acceptance criteria:**
- First call: generates `slugify(goal_text)[:48] + '-' + goal_id[:8]` and writes it to `comms_messages.slug`.
- Subsequent calls: returns the already-stored slug without overwriting it.
- Two concurrent calls for the same `goal_id` (threads or processes) both return the same slug; no duplicate insert error surfaces to the caller.
- The slug passes `_safe_topic` validation (bare slug, no path separators).
- `pytest tests/test_goal_slug.py` passes including a concurrency case.

### S1.3 — All collapse sites route topic=slug

**Who:** The supervisor infrastructure (transparent to end users).
**What:** Every call site that previously passed `topic=scope` now passes `topic=slug` — the
verified list: `goal_decomposer.py:246`, `goal_executor.py:52 + :223 + :317 + :321`,
`board_run.py:147+:247`, `terminal.py:39+:269+:307`, `orchestrator.py:336`,
`registry.py:148-149`, `goal_decomposer.py:239`.
**Why:** One missed site re-introduces the bug for that execution path.

Delivered by: Phase 1, Conversation 1.

**Acceptance criteria:**
- Grep for `topic=scope` in supervisor source returns zero matches (excluding comments and test fixtures).
- `board_run.start_board_run` accepts a `slug` parameter.
- `terminal.py` threads `storage_path` from the caller at all three sites; the hardcoded `pathly/plans/<topic>` pattern is absent.
- `_agent_done_watcher` at `terminal.py:86` is unchanged (`parent.parent.parent` still present).
- `pathly/goals/<slug>/` directory is created correctly for a project goal run.
- `pathly/plans/<slug>/` directory is created correctly for a feature run (regression check).

### S1.4 — Studio RESERVED set prevents phantom features

**Who:** A user looking at the Command Center left sidebar.
**What:** The `goals`, `lessons`, `explorations`, `debugs`, and `pipeline-walkthrough` directory
names are excluded from the feature list in the sidebar — they do not appear as phantom features.
**Why:** Once Phase 1 creates `pathly/goals/` on disk, any Studio build with the old RESERVED set
(`{plans, .archive}`) will surface `goals` as a feature.

Delivered by: Phase 1, Conversation 1.

**Acceptance criteria:**
- `commsStore.ts` RESERVED set contains exactly: `plans`, `.archive`, `goals`, `lessons`,
  `explorations`, `debugs`, `pipeline-walkthrough`.
- With a `pathly/goals/<slug>/` folder on disk, the sidebar feature list does not include an
  entry for `goals`.
- TypeScript compiles clean (`tsconfig.web.json`).

### S1.5 — SOLID split: terminal.py under 400 lines

**Who:** Any future developer touching terminal.py.
**What:** `terminal.py` is split into two or more files such that no resulting file exceeds
400 lines, and all existing tests pass.
**Why:** At 407 lines it is already over the SOLID limit; adding the storage-path threading code
would make it worse.

Delivered by: Phase 1, Conversation 1.

**Acceptance criteria:**
- No file in `supervisor/` that was produced by the split exceeds 400 lines.
- The `_agent_done_watcher` `parent.parent.parent` logic is preserved verbatim in whichever file contains it.
- All existing tests that import from `terminal.py` (or its replacement) pass without modification.

---

## Phase 2 — Artifact Contract

### S2.1 — Every pipeline artifact is guaranteed on the board

**Who:** Any agent consuming board context in a DAG run.
**What:** When any pipeline role (po, architect, planner, builder, reviewer, tester, retro,
explorer) writes its named artifact, a `comms_artifacts` row is created and an SSE
`artifact_attached` event fires — without requiring the agent to make a board POST.
**Why:** The structural guarantee must be server-side and deterministic; a fragment is advisory
and can be skipped by a misbehaving or aborted agent.

Delivered by: Phase 2, Conversation 2.

**Acceptance criteria:**
- After a planner stage completes, `comms_artifacts` contains a row for `IMPLEMENTATION_PLAN.md` keyed by `(scope, artifact_path)`.
- Calling `ensure_attached` twice for the same `(scope, artifact_path)` inserts exactly one row (idempotency).
- An SSE `artifact_attached` event is emitted when the row is first inserted.
- `pytest tests/test_artifact_reconcile.py` passes covering the FSM-gate path and the JSONL fallback path.
- `ensure_attached` uses application-level check-before-insert (no DB UNIQUE constraint on `comms_artifacts`).

### S2.2 — Planner produces DAG_PLAN.md in light mode

**Who:** A product owner or engineer whose goal is decomposed via the light (non-consultation) planner.
**What:** When a goal is decomposed in light mode (`_decompose_planner`), the planner writes a
`DAG_PLAN.md` file with a `## Tasks` table, rather than producing no artifact at all.
**Why:** The current light path explicitly instructs the agent "Do NOT create plan files" and
passes `skill=""`, so no artifact is ever written. This makes light-mode goals invisible on the board.

Delivered by: Phase 2, Conversation 2.

**Acceptance criteria:**
- `planning/dag-sketch.md` skill file exists in `core/skills/planning/`.
- `composition.yaml` contains an entry for `planning/dag-sketch` with `artifact-register`.
- `_decompose_planner` passes `skill="planning/dag-sketch"` (not `skill=""`).
- The "Do NOT create plan files" instruction is absent from `_decompose_planner`.
- After a light-mode decompose, `pathly/goals/<slug>/DAG_PLAN.md` exists and contains a `## Tasks` section.
- `artifact-manifest.yaml` contains the `planner.planning/dag-sketch` override with `{ file: DAG_PLAN.md, gate: '## Tasks' }`.

### S2.3 — Artifact manifest is the single source of truth for role→file→gate

**Who:** The skill composer, the FSM gate, and the reconciler.
**What:** `artifact-manifest.yaml` is the authoritative map of which role writes which file with
which gate pattern. The composer and FSM both read this file; they cannot drift apart.
**Why:** Duplicating the role→file mapping in the composer and the FSM independently creates a
class of bugs where one is updated but the other is not.

Delivered by: Phase 2, Conversation 2.

**Acceptance criteria:**
- `artifact-manifest.yaml` exists at `src/pathly_data/core/skills/artifact-manifest.yaml`.
- The manifest contains entries for all 9 pipeline roles: po, architect, web-researcher, designer,
  planner, reviewer, tester, retro, explorer.
- The `overrides` section contains `planner.planning/dag-sketch`.
- `validate_composition` fails the build if `planning/dag-sketch` is referenced in `composition.yaml` but absent from the skills directory.
- `pytest tests/test_compose.py` passes with regenerated snapshots.

### S2.4 — Artifact-register fragment writes artifact + ARTIFACTS.jsonl

**Who:** Any pipeline-role agent running a stage.
**What:** The `artifact-register.md` fragment instructs the agent to: (1) write the named artifact
to the injected `<out_path>`, (2) append one line to `ARTIFACTS.jsonl` in the storage folder,
(3) make an advisory board POST (skip if unreachable).
**Why:** The JSONL is the offline-proof fallback for the reconciler when `complete_stage` is not
called (single-agent / taskless runs).

Delivered by: Phase 2, Conversation 2.

**Acceptance criteria:**
- `fragments/artifact-register.md` exists at `src/pathly_data/core/skills/fragments/artifact-register.md`.
- A planner-stage run in test produces `ARTIFACTS.jsonl` with at least one line containing `{role, path, type, title, summary, ts}` keys.
- The JSONL path is the source the reconciler reads in the post-PTY path when `complete_stage` has not been called.
- Adapter sync (`pathly-setup claude --apply --repair` + `python -m build`) completes without error after Phase 2 changes.

### S2.5 — Phase 2 lands in exactly one commit

**Who:** The release engineer.
**What:** All seven Phase 2 artifacts (`artifact-manifest.yaml`, `artifact-register.md`,
`dag-sketch.md`, the `composition.yaml` entry, per-skill `artifact-register` attachments,
the `_decompose_planner` edit, and the 4-adapter sync output) are committed together.
**Why:** A partial deploy causes the planner to call `planning/dag-sketch` before the skill file
exists, which is a runtime error with no useful diagnostic.

Delivered by: Phase 2, Conversation 2.

**Acceptance criteria:**
- The git log shows a single commit containing all seven artifacts.
- Before the commit, `git diff --staged` shows all seven files.
- After the commit on a clean checkout, `python -m build` succeeds without errors.
- `validate_composition` (build-time check) passes on the committed state.

---

## Phase 3 — Sidebar

### S3.1 — Command Center sidebar shows Features, Goals, Lessons, Explorations

**Who:** A platform engineer or product owner using the Command Center.
**What:** The left sidebar rail shows collapsible grouped sections — one per card kind (Feature,
Goal, Lesson, Exploration). Empty groups are hidden. The collapsed rail shows colored dot clusters.
**Why:** PO_NOTES Definition of Success #5: sidebar completeness is required for the Command Center
to serve as a useful navigation hub.

Delivered by: Phase 3, Conversation 3.

**Acceptance criteria:**
- `CardSidebar` component exists in `studio/src/renderer/src/components/CommandCenter/CardSidebar/`.
- The sidebar shows a Features section, a Goals section (if any goals exist), a Lessons section (if any lessons exist), and an Explorations section (if any explorations exist).
- Empty groups are not rendered.
- Collapsed rail (48px) shows dot clusters for each non-empty section.
- TypeScript compiles clean via `tsconfig.web.json`.
- The feature `FeatureSidebar` still works as a fallback (flag-gated swap).
- `studio-responsiveness` rule: `min-width: 0` on flex children; no `overflow: hidden` near drop-up menus.

### S3.2 — cards store slice with derived features getter

**Who:** Any React component reading features from the store.
**What:** `commsStore` gains a `cards` slice. `features` is a derived getter (filter by `kind === 'feature'`) rather than a top-level key. `loadFeatures` is renamed `loadCards`.
**Why:** The current `set({features})` pattern erases other card kinds on every feature reload —
the store-shape bug described in DESIGN.md builder notes.

Delivered by: Phase 3, Conversation 3.

**Acceptance criteria:**
- `commsStore.ts` has a `cards: Card[]` property.
- `features` is accessible as a derived value (getter or selector), not a separate top-level key.
- `loadCards` replaces `loadFeatures` (old name absent from the store).
- Existing components that read `store.features` continue to compile and work correctly (backward-compatible access pattern).
- TypeScript compiles clean.

### S3.3 — Goal cards expose Decompose and Run actions

**Who:** A user clicking on a goal card in the sidebar.
**What:** Goal cards in the sidebar show Decompose and Run action buttons that call
`/comms/goals/decompose` and `/comms/goals/run` respectively.
**Why:** Goals are actionable entities, not just informational nodes.

Delivered by: Phase 3, Conversation 3.

**Acceptance criteria:**
- A goal card in the sidebar has a Decompose button that posts to `/comms/goals/decompose`.
- A goal card in the sidebar has a Run button that posts to `/comms/goals/run`.
- Both buttons are disabled when the backend is unreachable (degrade gracefully).
- Lesson card click opens the `.md` file in the MarkdownEditor panel.
- TypeScript compiles clean.

### S3.4 — CardKind types are defined and used consistently

**Who:** TypeScript compiler and any developer extending card types.
**What:** `types.ts` defines `CardKind = 'feature' | 'goal' | 'lesson' | 'exploration'`, a `Card`
superset, and `Feature = Card & {kind:'feature'}`.
**Why:** Without a shared type definition, each component casts independently and the types drift.

Delivered by: Phase 3, Conversation 3.

**Acceptance criteria:**
- `types.ts` exports `CardKind`, `Card`, and `Feature` as described.
- No TypeScript errors on the types (`tsc --noEmit` with `tsconfig.web.json`).
- `FeatureSidebar` still compiles using the new `Feature` type (it is a subtype of `Card`).
