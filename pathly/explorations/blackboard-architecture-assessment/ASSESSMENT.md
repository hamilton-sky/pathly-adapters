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
the classic pattern (Hearsay-II / HASP / BB1) are all present and mostly **enforced by construction**
(not merely conventional) — with the important qualifier, detailed below, that the fragment *wiring*
itself is enforced by the *default* composition rather than by a server-side check:

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

The enforcement mechanism is **fragments** — a prompt layer that owns the agent's channels back to
the system. On the **default composed** path, every return path is a fragment-owned one: board I/O
(`comms`) for knowledge/context, plus the `completion-report` fragment's `AGENT_DONE`→`fsm_events`
for the result/outcome (point 1). The property that matters is that there is **no *undeclared*
side-channel** — an agent can't stash state anywhere fragments don't route — which is what most
"multi-agent" tools lose on day one, and the reason Pathly gets auditability, resumability, and
multi-agent coherence at the design level. But **"structurally enforced" overstates it — there is no
server-side check that a spawned prompt actually contains the wire fragments.** Two
supported paths bypass the wiring:
1. **`prompt_override`** (`supervisor/board_run.py`) *replaces* the skill body outright — an override
   run can carry no `completion-report`/`comms-post` at all.
2. **The composition editor** — `PUT /skills/export` accepts *any* list of fragment names (including
   `[]`; it validates only "list of strings"), and `load_effective_manifest` **full-replaces** the
   skill's fragment list from that `skill_composition` row. A project override of `team/build` to a
   list missing `completion-report` drops the `AGENT_DONE` signal from **every ordinary composed
   run** — no `prompt_override` needed. The fragment *files* are packaged/un-editable, but *which
   fragments compose* is unguarded per-project.

So the guarantee is "enforced by the *default* composition," not "structurally locked." Both bypasses
argue for the same fix — a compose-time invariant checker (ISSUE-4) — plus recording overrides in the
audit model (ISSUE-3).

**The concept is right. The gap to "trustworthy" is a set of composition/board invariants that are
currently *trusted, not enforced*.** None is a rewrite. This doc enumerates them.

---

## 1. The blackboard mapping (why it's genuine, not marketing)

| Classic blackboard concept | Pathly realization | Enforced how |
|---|---|---|
| Shared blackboard (knowledge) | `comms_messages` (typed rows) + `comms_artifacts`; control/result state (`AGENT_DONE`) lives separately in `fsm_events` | single DB, `/comms/*` routes; `fsm_events` via `/runner/event` |
| Levels of abstraction | granularity axis: `task → goal` (within a board); `feature → project → global` is the *board-tier* axis, §2 Axis B — not this ladder | `goal_id`, `type`, `depends_on`; downward decompose (`goal_decomposer`) is real, upward completion is a computed rollup, not a state write (§2 Axis A) |
| Knowledge sources | CLI agents (architect/builder/reviewer/…) | spawned per stage/task from **packaged** agent text (`fsm_compose._load_agent_text` reads `pathly_data/core/agents/…`) — **not** the `agent_definitions` table (see §5) |
| KSs connect back through the board | via fragments (pure in `single`/`loop`; `team` adds a direct-spawn delegation tree via `spawn-rules`) | fragment *files* packaged; but the per-skill fragment *list* is DB-overridable + `prompt_override`-bypassable — see ISSUE-4 |
| KS trigger condition | task readiness (`depends_on` met) + role match | executor drains the DAG |
| Control component | passive FSM + supervisor loop + executor | `single` / `loop` / `team` |

**The load-bearing constraint is KS independence: agents share state only through fragment-owned
channels.** In `single`/`loop`, agents are stateless w.r.t. each other; `retrieve_board_context`
re-reads the board into every next prompt. This is the classic KS independence property, and Pathly
enforces it *structurally* (via fragments) rather than by documentation — the strongest thing in the
architecture. Two caveats keep "board is the *only* memory" from being literally true: the result
signal travels the `AGENT_DONE`→`fsm_events` channel, not the comms board (§0, item 1), and under
`team` the `spawn-rules` delegation tree adds a parent→child path (§0, item 2). So it's "shared state
only through governed channels," of which the comms board is the primary.

---

## 2. Three "scope"-like axes the narrative treats as one

This is the conceptual correction worth making permanent (now in `WHAT_IS_PATHLY.md §1a`). An earlier
draft of this doc got it wrong — it called the board tiers an "override chain." They are not; only
*abilities* override. Corrected model:

### Axis A — Abstraction levels (a blackboard property — but the upward half is a read-model)
```
task  →  goal
```
The ladder is real: `goal_id`/`type`/`depends_on` structure a goal into a task-DAG, and
`goal_decomposer` is a genuine **downward KS** (goal → tasks) — Hearsay-II's signal→word→phrase
decomposition. **But the upward half is not a state transition.** `complete_task` only sets the
task's `task_status='done'` (and computes newly-ready dependents); nothing writes the parent goal to
"done" (the sole UPDATE on a `type='goal'` row sets `executor`). Completion is *observed* by a
computed rollup (`get_goals_with_rollup` → `{done, total, …}`), a **read-model**, not an
upward-writing KS. So the abstraction hierarchy is real and inspectable, but "children complete ⇒
parent completes" is a derived view, not an implemented invariant — itself an instance of this doc's
observable-but-not-written theme.

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

**Why the conflation matters:** the three compose differently — levels decompose downward (and roll
up only as a computed view), board tiers aggregate across, abilities override by nearest. Calling all three "scope/layer" invites a
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

**What the code does:** `start_board_run` (`supervisor/board_run.py`) accepts `ability_ids` and
`prompt_override` — but **not** `excluded_sections`. The per-stage `{ability_ids, excluded_sections}`
is persisted in the **`stage_configs`** table (`db/queries/stage_configs.py`), and a **Sections trim
is realized by computing the trimmed prompt and delivering it via `prompt_override`** (the "Sections
gate … (prompt_override)" path), not by a separate board-run argument. The preview gate renders the
**composed** prompt before spawn; a Sections trim or full override changes what actually ships to the
CLI.

**As inspection — a real advance.** The hardest thing to debug in an agent system is that the prompt
is a black box assembled deep in the plumbing. Pathly makes the **blackboard→prompt projection a
glass box** you can read *and* edit at the moment of spawn. Exposing the control component's decision
*and its inputs* is strictly better than both hardcoded pipelines and opaque autonomous swarms.

**As mutation — a hole in the architecture's own thesis (ISSUE-3).** Pathly's foundational claim is
*"every prompt flows through fragments; fragments are un-editable; ONE authority."* A full
`prompt_override` **bypasses composition** — a deliberate hole in that wall. The section-trim gate is
careful (it locks *platform* fragments so a Sections trim can't drop board-CRUD wiring), but that
lock is **only on the trim path** — it does *not* cover the composition editor (§0, bypass 2: a
`skill_composition` override can drop `completion-report` server-side) or `prompt_override`. And the
moment an operator hand-edits a prompt, **that run is no longer reproducible from board state** — the
exact property that made the blackboard auditable.

**Fix (small, not polish):** a runtime override should itself be **posted back to the board as a
`type=decision` artifact** ("operator overrode stage X's prompt — diff attached"). Then the override
lives *inside* the audit model, and reproducibility is preserved as "board state + recorded
overrides." Treat as a correctness requirement before any unattended use.

---

## 5. User-authored KSs (extensibility as KS registration)

Letting users author agents / skills / abilities / flows is, structurally, **registering new
knowledge sources** — *for the layers actually wired into compose*. The tables split into two groups
by whether they reach the runtime:

- `skill_composition` (fragment-list overrides, `compose.load_effective_manifest`) **and** abilities
  (files, appended at compose time) are the only two DB/file layers that actually reach the
  **runtime** prompt — merged over the packaged YAML/`.md` seed at read time, without editing installed
  files (which `--repair` clobbers and `python -m build` regenerates). Correct, hard-won choice.
- `skill_definitions` / `agent_definitions` — **caveat: these do NOT feed the compose/spawn runtime.**
  `compose_skill` always reads the packaged body via `_read_skill_body()` (a file read), and
  `load_effective_manifest` applies only `skill_composition` fragment overrides — neither consults the
  definition tables. They are read by the skill-notebook editor (`blueprints/skills/editor_io.py`) and
  `services/config_service.py`, i.e. authoring/config surfaces. So a user who creates a project-scoped
  skill/agent *definition* does **not** thereby override the executable packaged prompt — an
  authored-vs-executed gap that is itself an instance of this doc's theme.

So the extensibility model *aspires* to the **same override-chain idea** as abilities and scope
tiers — **packaged defaults = seed; user contributions = DB-layer overrides** — and delivers it for
the two layers that reach the runtime (`skill_composition` + abilities). The definition tables are
the gap: authored/edited but not wired into compose, so "resolved at compose time, one authority" is
true for fragments/abilities but **not** for skill/agent definitions. Well-factored where it's
wired; incompletely wired where it isn't.

**Risk (ISSUE-4) — combinatorial safety, not architecture.** With `skill_composition` fragment
overrides, abilities, `prompt_override`, and user-authored flows composed across scope tiers, the
space of distinct prompt-assemblies explodes. **Nothing on the server validates that a spawned prompt
still carries the mandatory board-CRUD fragments** — not the composition editor (`/skills/export`
accepts `[]`), not `prompt_override` — nor that a user flow is acyclic. There is **no server-side
fragment lock at all** on the paths that *do* reach the runtime (only the section-trim gate locks
platform fragments, and only for trims). Fine for self-use; for a shared/product setting the missing
piece is a **compose-time invariant checker**.

---

## 6. Open issues (ranked)

| # | Issue | Where | Severity | Fix shape |
|---|---|---|---|---|
| **ISSUE-1** | Board identity is the `(board, scope)` **pair**, enforced only by query predicate — a read matching the wrong pair (missing `board` half, or an un-gated cross-tier union) mixes instances that share a `scope` value | `comms_messages` flat table; every `db/queries/comms_*` read | **Medium** (mostly design-gated: cross-tier aggregation is intentional + relevance-cutoff-gated, so this is a wrong-pair/un-gated-read risk, not a blanket bleed) | invariant test: assert every board read targets an explicit `(board, scope)` pair; consider a query wrapper that *requires* both args |
| **ISSUE-3** | Runtime `prompt_override` bypasses composition → run not reproducible from board | `supervisor/board_run.py` | **High** (breaks audit thesis) | post the override + diff back as a `type=decision` artifact; reproducibility = board + recorded overrides |
| **ISSUE-2** | Derived artifacts (reconstructed MD, diagrams) have no enforced provenance — versioning columns stubbed | `comms_artifacts.version/last_edit_*/supersedes` | **Medium** (stale-higher-level drift) | wire editor-save hooks to populate version/`supersedes`; link derived → source |
| **ISSUE-4** | No compose-time invariant that a spawned prompt keeps the wire fragments — `/skills/export` accepts an empty/trimmed fragment list and `load_effective_manifest` full-replaces, so a `skill_composition` override silently drops `completion-report`/`AGENT_DONE` from ordinary composed runs (also via `prompt_override`); flows aren't checked acyclic either | `skills/compose.py::load_effective_manifest`, `blueprints/skills/editor_io.py`, flow defs | **Medium→High** (a dropped `completion-report` = vanished + unbilled run; server-side, not just UI) | a `validate_composition()` gate: assert board-CRUD fragments present in the effective manifest; assert flow DAG acyclic; assert abilities resolve |
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
