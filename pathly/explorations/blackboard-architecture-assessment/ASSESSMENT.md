# Pathly as a Blackboard System — Architecture Assessment & Open Issues

**Author:** exploration session (Claude Opus 4.8) · **Date:** 2026-07-19 · **Baseline:** v2.22.0
**Method:** read against code at HEAD (branch `claude/app-state-discussion-kfuaca`) — schema
(`db/migrations.py`), compose path (`skills/compose.py`, `skills/abilities.py`,
`supervisor/board_run.py`), scope columns (`db/migrations_incremental.py`). Not doc-trusted.

> **Scope of this doc:** it is a *record* (a point-in-time critique), not a living contract.
> It states the classic-blackboard lens on Pathly and lists the seams that are **designed-for but
> not-yet-enforced**. The one durable clarification it produces — separating the *blackboard
> abstraction hierarchy* from the *scope-tier inheritance chain* — has been folded into the living
> north-star doc (`docs/WHAT_IS_PATHLY.md §1a`); everything else here is analysis, not a spec.

---

## 0. Bottom line

Pathly is a **faithful blackboard system**, not a metaphorical one. The three defining properties of
the classic pattern (Hearsay-II / HASP / BB1) are all present and **structurally enforced**, not
merely conventional:

1. **One shared blackboard for knowledge** — `comms_messages` + `comms_artifacts`, the shared
   *context/knowledge* substrate. (Not the *sole* store: the authoritative per-stage **result**
   signal — `AGENT_DONE`, written by the mandatory `completion-report` fragment via `/runner/event`,
   EVENTS.jsonl fallback — lives in the separate **`fsm_events`** control-event stream that the
   supervisor reads as the stage outcome. So "board is the only memory" is an oversimplification:
   knowledge lives on the comms board, control/result state lives in `fsm_events`.)
2. **Knowledge-source agents that connect back through the board** — they read the board and
   contribute back. This is pure under the `single`/`loop` executors (each agent is a fresh CLI
   process, no agent-to-agent calls). It is **partial under `team`**: on spawn-capable hosts the
   `spawn-rules` fragment has an orchestrator spawn `builder`/`reviewer`/`scout` sub-agents directly
   (a delegation tree), so invocation/result can travel parent→child outside the board.
3. **A separate control component** — passive FSM + supervisor loop + executor.

The enforcement mechanism is **fragments** (the un-editable prompt layer that owns all board I/O):
on the **composed** path, agents have no channel back to the system *except* the board. That is the
property most "multi-agent" tools violate on day one, and it is the reason Pathly gets auditability,
resumability, and multi-agent coherence at the design level. **Caveat (not absolute):** the
guarantee holds for composed prompts, but a nonempty `prompt_override` in `supervisor/board_run.py`
*replaces* the skill body rather than composing fragments — so the supported override path can spawn
an agent with no `completion-report` / `comms-post` wiring. "Structurally enforced" is therefore true
for the default path and **intentionally escapable** via override (see ISSUE-3 / §4) — which is
exactly why the override needs to be folded back into the audit model.

**The concept is right. The gap to "trustworthy" is a set of composition/board invariants that are
currently *trusted, not enforced*.** None is a rewrite. This doc enumerates them.

---

## 1. The blackboard mapping (why it's genuine, not marketing)

| Classic blackboard concept | Pathly realization | Enforced how |
|---|---|---|
| Shared blackboard (knowledge) | `comms_messages` (typed rows) + `comms_artifacts`; control/result state (`AGENT_DONE`) lives separately in `fsm_events` | single DB, `/comms/*` routes; `fsm_events` via `/runner/event` |
| Levels of abstraction | granularity axis: `task → goal` (within a board); `feature → project → global` is the *board-tier* axis, §2 Axis B — not this ladder | `goal_id`, `type` columns; decompose/aggregate KSs |
| Knowledge sources | CLI agents (architect/builder/reviewer/…) | `agent_definitions`, spawned per stage/task |
| KSs connect back through the board | via fragments (pure in `single`/`loop`; `team` adds a direct-spawn delegation tree via `spawn-rules`) | `core/skills/fragments/` (un-editable) |
| KS trigger condition | task readiness (`depends_on` met) + role match | executor drains the DAG |
| Control component | passive FSM + supervisor loop + executor | `single` / `loop` / `team` |

**The load-bearing constraint is "board is the only memory."** In `single`/`loop`, agents are
stateless w.r.t. each other; `retrieve_board_context` re-reads the board into every next prompt.
This is the classic KS independence property, and Pathly enforces it *structurally* (via fragments)
rather than by documentation — the strongest thing in the architecture. (Under `team` the
`spawn-rules` delegation tree weakens "only memory" to "primary memory"; see §0, item 2.)

---

## 2. Three "scope"-like axes the narrative treats as one

This is the conceptual correction worth making permanent (now in `WHAT_IS_PATHLY.md §1a`). An earlier
draft of this doc got it wrong — it called the board tiers an "override chain." They are not; only
*abilities* override. Corrected model:

### Axis A — Abstraction levels (a genuine blackboard property, within one board)
```
task  →  goal
```
A completed task-DAG *raises* a goal to done; a goal is itself a contribution at the goal level.
`goal_decomposer` is a **downward KS** (goal → tasks); completion aggregation is an **upward KS**
(tasks → goal). This is exactly Hearsay-II's signal→word→phrase abstraction ladder. **Faithful,
principled, and the best-realized part of the design.**

### Axis B — Board tiers (also a blackboard property — cross-board aggregation, NOT override)
```
feature  →  project  →  global
```
A board instance is the **`(board, scope)` pair**: `comms_messages.board` is the **tier**
(`feature`/`project`/`global`), `comms_messages.scope` is the **instance key** (feature name /
project_root / literally `global`). `retrieve_board_context` (`runner/comms_context.py`)
**aggregates across all three tiers by default** — feature-priority, with stricter per-tier cosine
cutoffs (`{feature:0.75, project:0.55, global:0.50}`) so only genuinely-close cross-tier items are
admitted. So the tiers **union relevant context**; they do **not** shadow each other. (My earlier
"resolve by override" was simply wrong for the board.) **The cutoff gates only *scored semantic*
matches**: governance (pending decisions + active escalations) is injected *unconditionally* across
tiers, and when embeddings are unavailable the recency fallback keeps unscored cross-tier rows — so
cross-tier isolation is relevance-gated for semantic hits only, not for governance or the
no-embedding path.

### Axis C — Ability / skill scopes (the ONLY override chain — a composition input, not the board)
```
project  overrides  global      (files)
```
A project ability **overrides** a global one with the same `<category>/<name>`
(`skills/abilities.py`). *This* is the lexical-scoping / prototype-chain override — and it lives in
the **composition layer** (files read at compose time), not in the message board.

**Why the conflation matters:** the three compose differently — levels aggregate upward, board tiers
aggregate across, abilities override by nearest. Calling all three "scope/layer" invites a
contributor to expect override where there is aggregation (and vice-versa). **Name them distinctly.**

### Structural consequence (a real correctness surface)
`board`, `scope`, and `goal_id` are **all plain columns on the same flat `comms_messages` table**.
"Which board am I on" is therefore a **query predicate, not a structural boundary** — and the
identity is the **`(board, scope)` pair**, not `scope` alone (a `scope`-only filter can mix records
when two tiers share a `scope` value). Note the invariant is **"reads target the intended
`(board, scope)` pairs,"** *not* "never cross tiers": cross-tier aggregation is a deliberate,
relevance-gated feature. The genuine risk is a read that matches the *wrong* pair (missing `board`
half, or an un-gated cross-tier union). This is the highest-value place for an invariant/test
harness (see §6, ISSUE-1).

---

## 3. The human-as-knowledge-source surface (the most original contribution)

Classic blackboard systems **do not model the human** — control is fully automated. Pathly's
whole-board manipulation surface is effectively **"the human as a first-class KS, operating at every
abstraction level"**:

- **Re-analyze the board different ways → post back** = a human-driven KS contribution.
- **Reorder / reconstruct MD artifacts, generate diagrams** = human-performed *abstraction-level
  translation* (sprawling artifact → digestible one) — literally a KS's job, done by a person.
- **Comments with competing approaches** = posting rival *partial solutions* for the control layer
  (or a downstream agent) to adjudicate.

**Why this is right:** abilities are **files composed at read-time exactly like fragments**
(`compose._read_fragment`; `##`-splittable into per-section toggles). The human's contribution enters
through the **same governed channel** as agent contributions — no side-door, no out-of-band override
that corrupts the audit trail. Most tools bolt human input on as an override that breaks provenance;
Pathly routes it through the same pipe. **Rate this highly; lead with it in positioning.**

**Reservation (ISSUE-2):** diagrams and reconstructed MD are *derived* artifacts, and the versioning
that keeps them honest is **stubbed**. `comms_artifacts.version` / `last_edit_*` / `supersedes`
columns exist but the schema comment admits they "stay at defaults — the editor-save + versioning
hooks that populate them are a deferred follow-up." A stale higher-level artifact that no longer
reflects the level below it is *the* classic blackboard failure mode. Anticipated (columns present),
not closed.

---

## 4. Runtime prompt control — the sharpest double edge

**What the code does:** `start_board_run` accepts `prompt_override`, `ability_ids`,
`excluded_sections` (`supervisor/board_run.py`); `stage_configs` persists per-stage
`{ability_ids, excluded_sections}`; the preview gate renders the **composed** prompt before spawn; a
Sections trim or full override changes what actually ships to the CLI.

**As inspection — a real advance.** The hardest thing to debug in an agent system is that the prompt
is a black box assembled deep in the plumbing. Pathly makes the **blackboard→prompt projection a
glass box** you can read *and* edit at the moment of spawn. Exposing the control component's decision
*and its inputs* is strictly better than both hardcoded pipelines and opaque autonomous swarms.

**As mutation — a hole in the architecture's own thesis (ISSUE-3).** Pathly's foundational claim is
*"every prompt flows through fragments; fragments are un-editable; ONE authority."* A full
`prompt_override` **bypasses composition** — a deliberate hole in that wall. The code is careful
(platform fragments are locked; you can trim sections but not delete board-CRUD wiring), which shows
the author saw the danger. But the moment an operator hand-edits a prompt, **that run is no longer
reproducible from board state** — the exact property that made the blackboard auditable.

**Fix (small, not polish):** a runtime override should itself be **posted back to the board as a
`type=decision` artifact** ("operator overrode stage X's prompt — diff attached"). Then the override
lives *inside* the audit model, and reproducibility is preserved as "board state + recorded
overrides." Treat as a correctness requirement before any unattended use.

---

## 5. User-authored KSs (extensibility as KS registration)

Letting users author agents / skills / abilities / flows is, structurally, **registering new
knowledge sources.** The tables back it cleanly and *consistently with the rest of the override
model*:

- `skill_definitions` / `agent_definitions` — DB-backed, `project_root`-scoped; user content
  overrides packaged defaults **without editing installed files** (which `--repair` clobbers and
  `python -m build` regenerates). Correct, hard-won choice.
- `skill_composition` — per-project fragment-list overrides merged over the YAML seed at read time
  (`compose.load_effective_manifest`).

So the extensibility model is the **same override-chain idea** as abilities and scope tiers, applied
to the KS registry: **packaged defaults = seed; user contributions = DB-layer overrides; resolved at
compose time. One authority, layered.** Well-factored.

**Risk (ISSUE-4) — combinatorial safety, not architecture.** With user-authored agents
(`tools_json`, `can_spawn_json`), skills, abilities, *and* flows, composed across three scope tiers
with runtime overrides on top, the space of distinct prompt-assemblies explodes. Nothing validates
that a user-authored agent's skill still receives the mandatory board-CRUD fragments, or that a user
flow is acyclic. The un-editable-fragment lock is the *only* guardrail. Fine for self-use; for a
shared/product setting the missing piece is a **compose-time invariant checker**.

---

## 6. Open issues (ranked)

| # | Issue | Where | Severity | Fix shape |
|---|---|---|---|---|
| **ISSUE-1** | Board identity is the `(board, scope)` **pair**, enforced only by query predicate — a read matching the wrong pair (missing `board` half, or an un-gated cross-tier union) mixes instances that share a `scope` value | `comms_messages` flat table; every `db/queries/comms_*` read | **Medium** (mostly design-gated: cross-tier aggregation is intentional + relevance-cutoff-gated, so this is a wrong-pair/un-gated-read risk, not a blanket bleed) | invariant test: assert every board read targets an explicit `(board, scope)` pair; consider a query wrapper that *requires* both args |
| **ISSUE-3** | Runtime `prompt_override` bypasses composition → run not reproducible from board | `supervisor/board_run.py` | **High** (breaks audit thesis) | post the override + diff back as a `type=decision` artifact; reproducibility = board + recorded overrides |
| **ISSUE-2** | Derived artifacts (reconstructed MD, diagrams) have no enforced provenance — versioning columns stubbed | `comms_artifacts.version/last_edit_*/supersedes` | **Medium** (stale-higher-level drift) | wire editor-save hooks to populate version/`supersedes`; link derived → source |
| **ISSUE-4** | No compose-time invariant that every spawned prompt contains the wire fragments / every flow is acyclic | `skills/compose.py`, flow defs | **Medium** (grows with user-authoring) | a `validate_composition()` gate: assert board-CRUD fragments present; assert flow DAG acyclic; assert abilities resolve |
| **ISSUE-5** | Narrative conflates abstraction levels with scope tiers | docs | **Low** (clarity/onboarding) | ✅ addressed in `WHAT_IS_PATHLY.md §1a` |

**Through-line:** every issue is the same species — *guarantees resting on invariants that are
currently trusted, not enforced.* One flat table partitioned by predicate; overrides layered three
deep; user-authored KSs; runtime edits. The architecture is sound; the maturation work is
**turning trusted invariants into checked ones**, and it is smaller than it looks because the author
has already left the seams (reserved columns, fragment locks, spawn-time-adapter billing) where the
checks belong.

---

## 7. Other insights encountered during research (not the main thread)

- **The billing chokepoint is a good model for where invariants belong.** `POST
  /runner/terminal/result` is the *single* run-keyed billing authority, using the **spawn-time**
  adapter (not the racy live `current_adapter`). This "one chokepoint, keyed by run_id" pattern is
  exactly the shape ISSUE-1/ISSUE-4 want: a single place every write must pass through. The telemetry
  layer already demonstrates the team can build these; the board-read layer hasn't had one applied yet.
- **"Headless" ≠ "unattended."** The supervisor spawns PTYs via `TERMINAL_SPAWN` SSE into the Electron
  renderer — Studio is a *required host*, not optional. "Headless" here means *no human in the
  per-step loop*, not serverless. `runner/invoke.py` exists but is used only by the separate
  `runner/cli.py`, not the supervisor. Honest-scope item, orthogonal to the blackboard critique.
- **Parallelism is serial-only inside a goal's DAG.** `_run_loop` hardcodes
  `SerialIsolation(max_concurrency=1)`; `LaneIsolation` exists (tests only); `WorktreeIsolation` is
  `NotImplementedError("P3")`. The blackboard data model is already parallel-ready (the board *is* a
  shared queue) — which is precisely why P3 is "flip k>1 by lane," not a redesign. But it also means
  ISSUE-1 (`(board, scope)`-pair isolation) gets *sharper* under parallelism, because concurrent
  lanes reading the same flat table with wrong-pair predicates is where a mixup becomes a race.
- **"One authority, everything else a projection" is the real north star** (commit `1a970bf`), and it
  is *mostly* true: `agent_invocations` is a projection of the `AGENT_DONE` event stream; `BOARD.json`
  mirrors the DB; abilities/skills resolve from files+DB overrides at read time. The two places the
  "one authority" claim is currently *aspirational rather than proven* are exactly ISSUE-1 (tier
  isolation) and ISSUE-3 (runtime overrides) — close those and the slogan becomes a theorem.
