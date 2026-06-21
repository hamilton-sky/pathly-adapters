# Build Prompts — Board Context-Retrieval

> **✅ ALL FOUR PHASES BUILT (2026-06-22) — do NOT re-run these prompts.**
> Implemented on branch `shammai/comms-board-contex`, commits `88d9730b` (P1) →
> `01f106a6` (P2) → `c2b845df` (P3) → `53f28fd7` (P4); 824 tests pass; unpushed,
> awaiting review. These prompts are kept as the build record. Phase 3's adversarial
> review caught + fixed a path-traversal hole and an index-wipe bug. Deferred follow-up:
> the §3a Studio upload backend picker (Off/Local/Haiku) — renderer work, not built.

Phase-by-phase kickoff prompts for implementing
[`DESIGN_SPEC-context-retrieval.md`](DESIGN_SPEC-context-retrieval.md).

> **Scope — read only these.** This is the **context-retrieval** sub-feature. The implementing
> agent should read ONLY `DESIGN_SPEC-context-retrieval.md`, `DESIGN_SPEC-local-inference.md`,
> and the layer `CLAUDE.md` files. Everything else in this folder — `ROADMAP.md`,
> `GOALS-DAG-EXECUTORS.md`, `DAG-SCHEDULER-ARCHITECTURE.md`, `BOARD-*-SPEC.md`,
> `TASKGRAPH-DESIGN.md`, `HQ-COMMAND-CENTER.md`, `phases/`, `_archive/` — describes the broader
> **Board→Goals→DAG** initiative and a **different, unrelated set of phases (P0a/0b/P1/P2/P3)**.
> Background only; do not implement from them. The **"Phase 1–4" below are specific to THIS
> feature** (spec §9.1) and are unrelated to the dispatcher's "Phase 1."

**How to use:** paste **Phase 1** into a fresh session. When it finishes, verifies, and
commits, glance at the diff, then paste the next phase. Keep it the **same session** so the
spec stays in context (each prompt still names the spec path so it works even if context
compacts). The spec's §6 is the ordered call-site checklist; §9.1 is the four-phase
sequence; §10 holds the resolved decisions (note **Q3=(b)** — the planner posts each
advisory file as a `type="artifact"` message). Phases 1–2 and 4 are additive/low-risk;
**Phase 3 is the high-blast-radius one** — review it closely. Per repo policy, each phase
commits but does **not** push without an explicit request.

---

## ⚠ Validation note — revalidated against `master` on 2026-06-21

The spec was authored against `shammai/cli-controls` (2026-06-18). **Phase 0b + P1 landed
since**, so before pasting any phase below, know:

1. **All `file:line` refs are approximate, not exact.** The comms blueprint grew ~50 lines
   (`goals/run`, `goals/decompose`). **Locate every edit site by symbol / route name, never by
   line number.** Structural anchors are all verified present on master:
   additive-migration list still ends at `executor` (`db/migrations.py:380`) ·
   `comms_artifacts` CREATE (`:252`) · `insert_artifact` (`db/queries/comms.py:318`,
   idempotent per `(message_id,path)`) · artifact-post branch (`blueprints/comms.py` ~`:246-267`) ·
   `/comms/attach` (`:655`) · `/comms/artifacts` GET (`:756`) · `embed_async`
   (`runner/embeddings.py:46`) · `retrieve_board_context` / `board_context_for`
   (`runner/comms_context.py:95` / `:296`). The F12 "greenfield" precondition still holds
   (no `context_refs` / `section` / `anchor` anywhere).

2. **`plan.md` Step 6 materially changed — merge, don't replace.** Phase 0b rewrote Step 6 to
   post a `type='goal'` first and stamp `goal_id` on each task. Phase 2's plan.md edits must
   **merge** advisory-artifact posting + `context_refs` into that existing goal-first block; the
   pre-0b Step 6 the spec snapshots no longer exists.

3. **Validate-at-write splits across Phase 2 and Phase 3.** §2.4's resolution gate calls
   `get_section`, which does not exist until Phase 3. So **Phase 2 implements the `context_refs`
   *shape* guard only**; the **resolve-and-relax-unresolved-anchors gate lands in Phase 3**, after
   `get_section`. This is consistent with §2.4's "best-effort — on resolver error keep the ref
   as-authored," which Phase 2 satisfies by simply storing refs as-derived.

---

## Phase 1 — heading convention (no code, lowest risk)

```
Implement Phase 1 of pathly/plans/comms-board/DESIGN_SPEC-context-retrieval.md.

First read (context for all phases): that spec (§6 = ordered call-site checklist; §9.1 =
the 4 phases; §10 = RESOLVED decisions, note Q3=(b)); pathly/plans/comms-board/
DESIGN_SPEC-local-inference.md (used in Phase 4); src/pathly_orchestrator/CLAUDE.md and
src/pathly_data/CLAUDE.md (layer rules + propagation commands).

PHASE 1 (§6 rows 7 + 10) — make the planner author matching "## Phase N" headings in
EDGE_CASES.md / HAPPY_FLOW.md / ARCHITECTURE_PROPOSAL.md so sections become anchor-addressable:
- core/skills/planning/plan.md — add the authoring instruction.
- core/templates/plan/{EDGE_CASES,HAPPY_FLOW,ARCHITECTURE_PROPOSAL}.template.md — reinforce
  the "## Phase N" structure.

Propagate: pathly-setup claude --apply --repair ; python -m build. Commit this phase.
Do NOT push. Then stop and summarize.
```

---

## Phase 2 — `context_refs` plumbing + advisory artifacts

```
Continue: Phase 2 of pathly/plans/comms-board/DESIGN_SPEC-context-retrieval.md
(re-read §2, §6 rows 1/2a/6a/7, §10 Q1+Q3 if not in context). Additive; does not touch the
P1 dispatcher.

- db/migrations.py — add comms_messages.context_refs TEXT (additive, mirrors goal_id/executor;
  append after the executor tuple at the end of _add_additive_migrations).
- db/queries/comms.py — post_message gains a context_refs kwarg (JSON, like depends_on).
- http_server/blueprints/comms.py — /comms/post accepts context_refs with the SHAPE guard ONLY
  (list of {artifact:str, anchor?:str|null}). The §2.4 resolve-against-index gate is Phase 3
  (it needs get_section); for now store refs as-derived (that IS §2.4's best-effort fallback).
- core/skills/planning/plan.md Step 6 — MERGE into the existing Phase-0b goal-first block (it
  already posts a type="goal" + stamps goal_id; do NOT replace it). (a) post each advisory file
  as a type="artifact" message, capturing message_id [Q3=(b)]; (b) emit context_refs per phase
  task: {artifact, anchor:"phase-N"} for EDGE_CASES/HAPPY_FLOW, ARCH optional (whole-file
  anchor:null for short proposals) [Q1]. Keep the idempotency + fail-silent guards.

Verify: python -m pytest tests/ -q. Propagate: pathly-setup claude --apply --repair ;
python -m build. Commit. Do NOT push. Stop and summarize.
```

---

## Phase 3 — hydration engine + Board Catalog (the high-risk one)

```
Continue: Phase 3 of pathly/plans/comms-board/DESIGN_SPEC-context-retrieval.md
(re-read §3, §4, §5, §5a, §6 rows 2–9, §7). High blast radius — review carefully.

- db/migrations.py — comms_artifact_sections table + index; indexed_mtime/indexed_hash.
- db/queries/comms.py — reindex_artifact_sections, get_artifact_sections, get_section,
  find_or_create_artifact_by_path (minimal defensive resolver, §6 row 2d), list_artifacts_catalog.
- runner/sections.py (NEW) — parse_sections, slugify_heading, file_fingerprint (§3).
- runner/hydrate.py (NEW) — hydrate_section, ensure_indexed (staleness mtime→hash, §3.4),
  index_artifact_async; never raises.
- http_server/blueprints/comms.py — GET /comms/artifacts/<id>/section + path form (§4, with
  path-traversal guard); fire index_artifact_async on type="artifact" post; board/scope
  listing form on GET /comms/artifacts (§5a.4). ALSO land here (deferred from Phase 2): the
  §2.4 validate-at-write resolution gate on /comms/post — now that get_section exists, resolve
  each {artifact, anchor}; relax unresolved → whole-file (anchor:null) + board-nudge warning;
  best-effort — a resolver error keeps the ref as-authored (never fail the task post).
- runner/comms_context.py — optional task_id param; hydrate context_refs → emit "### 📎
  Referenced context" between Governance and Context; default None ⇒ byte-identical to today.
- core/skills/development/drain-dag.md + the reviewer skill — add the per-ref /section hydrate step.

RIGOR: adversarial self-review (path traversal, layer direction db<runner<http_server,
stale-index race). Run the §7 backward-compat matrix as explicit tests (no context_refs,
no task_id, NULL summaries, never-indexed artifact, legacy plan).

Verify: python -m pytest tests/ -q. Propagate: pathly-setup claude --apply --repair ;
python -m build. Commit. Do NOT push. Stop and give a detailed summary + anything uncertain.
```

---

## Phase 4 — wire the offline summarizer

```
Continue: Phase 4 of pathly/plans/comms-board/DESIGN_SPEC-context-retrieval.md
(re-read §9.1 step 4 + DESIGN_SPEC-local-inference.md — call the summarizer, do NOT redesign it).

- At index time (runner/hydrate.py path), call the inference service (minilm/ollama/
  spawn-claude-haiku; NO web API) to fill comms_artifacts.summary + per-section summary.
- db/queries/comms.py — update_artifact_summary / update_section_summary writeback hooks
  (§6 row 2e), fired async after indexing (mirror embed_async).
- Confirm the catalog shows rich descriptions and the 💡 ranking improves — and that
  everything still works with the summarizer off (summary NULL → catalog falls back to
  path/title, §7).

Verify: python -m pytest tests/ -q. Propagate if any core/ files changed. Commit.
Do NOT push. Summarize the end-to-end result.
```
