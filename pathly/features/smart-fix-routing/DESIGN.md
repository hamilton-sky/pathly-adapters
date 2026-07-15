# DESIGN — Smart Fix-Routing

Route a review/test failure FIRST to the role that owns its root-cause artifact
(po / planner / architect / designer), which produces the corrected
artifact/decision, THEN the builder implements it. A pure implementation defect
still goes straight to the builder, unchanged.

Status: DESIGN (no code written). Builder-ready.

---

## TL;DR — the decision

**The FSM already supports the routing we need. No new routing engine, no new
state, no supervisor change.** The mechanism is `route_feedback` +
`feedback_routing` (feedback FILE → responsible role), which already runs as the
first step of every `next_action` / `complete_stage` and already routes
non-current-state roles (e.g. `ARCH_FEEDBACK.md → architect`) while the feature
stays in `REVIEWING`.

Smart-fix-routing is delivered by:

1. **Classification vocabulary** — extend `classify_feedback.py` from 2 tags
   (`[REQ]`/`[ARCH]`) to 5: `[REQ]` `[PLAN]` `[ARCH]` `[DESIGN]` `[IMPL]`.
2. **One tag ⇒ one feedback file ⇒ one role** — the reviewer/tester writes the
   failure into the role-specific file named by its dominant class. Two of the
   files already exist and route today (`ARCH_FEEDBACK.md → architect`,
   `REQUIREMENT_GAP.md → po`); we add `PLAN_FEEDBACK.md` and `DESIGN_FEEDBACK.md`.
3. **Existing filename→role routing** carries it — we only add map entries to the
   flow YAMLs and (small hardening) make the priority order explicit.
4. **A real "fix mode" prompt** for a routed non-builder role — enrich the thin
   `build_prompt_for_agent` so architect/planner/designer/po get "read the
   failure, correct YOUR artifact, hand the implementation to the builder."

The classification tag, the feedback filename, and the role are the **same single
system** (`[ARCH]` ⇄ `ARCH_FEEDBACK.md` ⇄ `architect`) — not a parallel one.

```
BEFORE:  REVIEWING ──(REVIEW_FAILURES.md)──► builder ──► re-review

AFTER:   REVIEWING ──classify──► {po | planner | architect | designer}
                                    └─ fix root-cause artifact ─► builder ─► re-review
         pure [IMPL] failure ─────────────────────────────────► builder ─► re-review  (unchanged)
```

---

## 1. Routing mechanism decision

### 1.1 Does the FSM support conditional routing? — YES, three ways

Evidence (`src/pathly_orchestrator/fsm/engine_transitions.py`):

| Mechanism | Where | Condition | Result |
|---|---|---|---|
| `feedback_routing` | `route_feedback` (line ~323–346) | an open `feedback/<FILE>.md` exists | routes that file to a **role** (any role, not just the current state's) |
| `escalation_routing` | `_resolve_feedback_target` (line ~238–263) | a failure file's **retry count** ≥ tier threshold | escalates that file **upstream** by round (round 3 → specialist, round 4 → human) |
| `evaluate_transition_rules.on_content` | line ~68–84 | a file **contains** a substring/regex | picks the next **state** |

`route_feedback` runs **first** in both entry points and, when it finds an open
feedback file, returns a *blocked* response carrying `target_agent` **without
transitioning state** — see `next_action` (`fsm_ops.py:254–279`) and
`complete_stage` (`fsm_ops_complete.py:81–105`). The supervisor then spawns that
target as a fresh stage (`supervisor/orchestrator_stage.py:161–205`). This is
exactly "route REVIEWING's failure to a non-REVIEWING role" — the machine we need
already exists and is already exercised (`ARCH_FEEDBACK.md → architect`).

**What is NOT supported (and why we don't add it):** routing on the *content
classification inside a single file* (read `REVIEW_FAILURES.md`, detect `[ARCH]`,
send to architect **for that one file**, then hand the same file to the builder).
That would require the router to read file bodies AND a change to how the loop
resolves files — see the rejected alternative below.

### 1.2 The mechanism: tag ⇄ file ⇄ role ⇄ artifact

The reviewer classifies each failure by **root cause** and writes it into the
file for that class. Routing is then the existing filename→role map.

| Class tag | Feedback file | Routed role | Artifact the role corrects |
|---|---|---|---|
| `[REQ]` | `REQUIREMENT_GAP.md` | `po` | `USER_STORIES.md` / `PO_NOTES.md` (acceptance + scope) |
| `[PLAN]` | `PLAN_FEEDBACK.md` | `planner` | `IMPLEMENTATION_PLAN.md` (phases / task DAG) |
| `[ARCH]` | `ARCH_FEEDBACK.md` | `architect` | `ARCHITECTURE_PROPOSAL.md` |
| `[DESIGN]` | `DESIGN_FEEDBACK.md` | `designer` | `DESIGN.md` |
| `[IMPL]` | `REVIEW_FAILURES.md` | `builder` | source code (default / unchanged) |
| `[ACCEPT]`→`[REQ]` | `ACCEPTANCE_QUESTION.md` | `po` | `USER_STORIES.md` (test-stage only) |

`ARCH_FEEDBACK.md` and `REQUIREMENT_GAP.md` already exist and route in
`team-build.flow.yaml`; only `PLAN_FEEDBACK.md` and `DESIGN_FEEDBACK.md` are new
names. The tag→file mapping mirrors `artifact-manifest.yaml`
(`src/pathly_data/core/skills/artifact-manifest.yaml`), the machine-readable
role→artifact SSOT.

### 1.3 Why role-specific FILES, not one tagged file (the load-bearing constraint)

The supervisor's feedback loop **force-deletes the routed file after exactly one
hop**. In `supervisor/orchestrator_stage.py`, after spawning the target it sets
`resolved = [file_]` (line 204) and the next `complete_stage` unlinks that file
(`fsm_ops_complete.py:33–41`). This exists to guarantee loop progress.

Consequence: **a single `REVIEW_FAILURES.md` cannot survive an architect→builder
hand-off** — if the architect downgrades tags in place, the file is deleted before
the builder ever sees it. Distinct per-role files each survive the *other's*
force-delete, so:

```
route picks highest-priority open file ─► architect fixes ARCHITECTURE_PROPOSAL.md
      (ARCH_FEEDBACK.md)                    + writes/append REVIEW_FAILURES.md ([IMPL])
                                            + deletes ARCH_FEEDBACK.md
   next route ─► REVIEW_FAILURES.md ─────► builder implements ─► deletes it
   next route ─► (none) ─► REVIEW_INCOMPLETE gate ─► reviewer re-reviews ─► PASS
```

Each hop is one blocked-response spawn; the feature stays in `REVIEWING`
throughout (po/planner/architect/designer have no state in the team flow — they
can only exist as feedback targets, which is precisely this mechanism).

### 1.4 Rejected alternative — content-router in `route_feedback`

Make `route_feedback` read `REVIEW_FAILURES.md`, detect the dominant tag, and
return the upstream role. **Rejected** because:

- The force-delete (1.3) destroys the one file before the builder hop, so it needs
  *either* a supervisor "don't auto-resolve" flag *or* a rework of the proven
  force-delete progress guarantee — new surface area on the most safety-critical
  loop, higher regression risk to every linear flow.
- It duplicates classification logic server-side that the reviewer already does
  better (semantic judgment vs keyword regex).
- The file-based path reuses infrastructure that is **already built** in
  `team-build.flow.yaml` (`architect`/`designer`/`po`/`planner` feedback targets).

Position: **role-specific files is the cleaner architecture fit and the lower-risk
change.** It is the natural completion of routing that already half-exists.

### 1.5 Priority ordering — small hardening (recommended)

`route_feedback` returns the **first** matching file in
`feedback_routing.items()` order (engine_transitions.py:331) — i.e. priority =
dict-insertion order in the YAML. Upstream-first ordering (fix the requirement
before the plan before the architecture before the design before the code) is now
**load-bearing**, and dict order can be disturbed by the DB round-trip
(`db/queries/flow_graph_ops.py`) or the Studio serializer
(`serializeFlow.ts`). Make it explicit:

- Add an optional `feedback_priority:` list to the flow schema, and in
  `route_feedback` sort matched files by that list (fallback: current dict order).
- Canonical order:
  `HUMAN_QUESTIONS > BLOCKED_ON_HUMAN > REQUIREMENT_GAP > PLAN_FEEDBACK >
   ARCH_FEEDBACK > DESIGN_FEEDBACK > REVIEW_FAILURES > TEST_FAILURES`.

This is ~15 lines in `route_feedback`, layer-clean (fsm layer), and it makes
"upstream cause fixed first" deterministic regardless of serialization.
`escalation_routing` (retry tiers) is **orthogonal and unchanged** — smart-routing
picks the *initial* target by root cause; escalation still bumps a *stuck* file
upstream by retry count. They compose.

---

## 2. Per-flow plan

| Flow | Change | Reason |
|---|---|---|
| **team** (`team.flow.yaml`) | **Enrich** `feedback_routing` (+`PLAN_FEEDBACK→planner`, `DESIGN_FEEDBACK→designer`, `REQUIREMENT_GAP→po`, `ACCEPTANCE_QUESTION→po`; `ARCH_FEEDBACK→architect` already present). **Add** `escalation_routing` (missing today). **Add** `feedback_priority`. | Full pipeline has all roles; primary target of the feature. |
| **team-build** (`team-build.flow.yaml`) | **Add** `PLAN_FEEDBACK→planner`, `DESIGN_FEEDBACK→designer` (already has `ARCH_FEEDBACK`, `REQUIREMENT_GAP`, `ACCEPTANCE_QUESTION`, `PO_QUESTIONS`). Reorder / add `feedback_priority`. | Goal `team` executor flow; reuses the same `team/review`+`team/test` skills, so it inherits the split for free. |
| **test** (`test.flow.yaml`) | Mirror team's `feedback_routing` enrichment + `feedback_priority`. | Uses `team/review`+`team/test`; has REVIEWING+TESTING loops. |
| **debug** (`debug.flow.yaml`) | **Minimal**: optionally add `ARCH_FEEDBACK→architect` for the rare "the fix needs a design change" case. Default `TEST_FAILURES→builder` stays. | Debug has no requirements/plan/design artifacts (`INVESTIGATING→…→FIXING→VERIFYING`); a verify failure is almost always an impl defect. Full smart-routing is N/A. |
| **quick-fix** (`quick-fix.flow.yaml`) | **No change (N/A).** | Nano/lite fast path (`SCOPING→FIXING→VERIFYING`); no plan/design/PO artifacts to correct. |
| **consultation / feature-consultation / project-consultation** | **No change (N/A).** | Decompose flows (`PO→architect→researcher→designer→planner`); **no review/test loop**. Their `feedback_routing` is clarification-only and already role-specific. |
| **explore** | **No change (N/A).** | No build/review/test loop. |

---

## 3. Role "fix mode"

The routed non-builder role is spawned in the **headless path** via
`build_prompt_for_agent(target_agent, storage_path)`
(`fsm_compose.py:367–377`), which today returns only the **raw role contract** +
`Feature`/`Storage path`. It does **not** tell the role there is a failure to fix,
which artifact to correct, or to hand off to the builder. The role `.md` contracts
(`architect.md`, `po.md`, `planner.md`, `designer.md`) are generic and carry **no
fix mode**. So fix mode must be injected at the **prompt** layer, in one place.

### 3.1 Enrich `build_prompt_for_agent` (single change, all roles, all flows)

- Add a param `feedback_file: str | None`. Thread `feedback["file"]` from the 3
  call sites: `fsm_ops.py:267`, `fsm_ops_complete.py:93` and `:187`.
- When `feedback_file` is a **routed root-cause file** (i.e. the target is not
  `builder`/`reviewer`/`human`), append a **fix-mode contract** block built from a
  small role→artifact map (reuse `artifact-manifest.yaml`'s `roles:` section):

```
## Fix mode — you are resolving a routed review/test failure

A reviewer/tester traced a failure to YOUR artifact. You are NOT re-running your
whole stage — you are patching the specific decision that was wrong.

1. Read  <feature_path>/feedback/<FEEDBACK_FILE>   (the failure + why it is yours).
2. Correct YOUR artifact: <ROLE_ARTIFACT>  (if absent, the nearest equivalent —
   IMPLEMENTATION_PLAN.md / USER_STORIES.md). Change only what the failure requires.
3. Hand off to the builder: if the corrected artifact implies code changes, write
   (or APPEND to) <feature_path>/feedback/REVIEW_FAILURES.md a short [IMPL] section
   naming the change ("implement per updated ARCHITECTURE_PROPOSAL.md §X").
   If the correction is decision-only (no code), skip this — the re-review gate
   will re-verify.
4. Delete <feature_path>/feedback/<FEEDBACK_FILE> when your artifact is corrected.
5. Report what changed. Do NOT run pathly-fsm-call / complete-stage (supervisor owns the FSM).
```

Role→artifact used for `<ROLE_ARTIFACT>`: `po → USER_STORIES.md`,
`planner → IMPLEMENTATION_PLAN.md`, `architect → ARCHITECTURE_PROPOSAL.md`,
`designer → DESIGN.md`.

This is layer-clean (`fsm_compose.py`, fsm layer), DRY (one block, all roles), and
leaves the builder path (`target == builder`) byte-identical to today.

### 3.2 Teach the reviewer/tester to split (both delivery paths)

The reviewer writes the failure files in **both** headless and interactive modes,
so the split instruction lives in the composed skills + the shared fragment:

- **`team/review.md`** — Phase 3 review prompt + "Feedback routing after reviewer":
  extend the current "arch → `ARCH_FEEDBACK.md`, impl → `REVIEW_FAILURES.md`" split
  to the full 5-way classification (add PLAN/DESIGN/REQ files).
- **`team/test.md`** — Fix loop: split acceptance-criteria failures
  (`[REQ]`/`[ACCEPT]`) into `ACCEPTANCE_QUESTION.md → po`; impl failures stay
  `TEST_FAILURES.md → builder`.
- **`fragments/feedback-protocol.md`** — the shared contract composed into review +
  test: replace the priority line + add the tag ⇄ file ⇄ role table so every
  stage agent classifies identically.
- **`agents/quality/reviewer.md`** / **`tester.md`** — add the tag vocabulary to the
  output format so the reviewer *sub-agent* tags each violation
  `[REQ]/[PLAN]/[ARCH]/[DESIGN]/[IMPL]` at the point of judgment.

---

## 4. File-by-file change list

### Data / flows (`src/pathly_data/core/flows/`)
- `team.flow.yaml` — enrich `feedback_routing`; add `escalation_routing`; add
  `feedback_priority`.
- `team-build.flow.yaml` — add `PLAN_FEEDBACK→planner`, `DESIGN_FEEDBACK→designer`;
  add `feedback_priority`.
- `test.flow.yaml` — enrich `feedback_routing`; add `feedback_priority`.
- `debug.flow.yaml` — optional `ARCH_FEEDBACK→architect` only.
- (`quick-fix`, `explore`, all `*consultation*` — untouched; N/A.)

### Hooks (`src/pathly_hooks/`)
- `classify_feedback.py` — extend the vocabulary to 5 tags. Add keyword regexes
  `_PLAN_QUESTION` (plan/phase/task/sequence/dependency), `_DESIGN_QUESTION`
  (ui/ux/layout/component/visual/style), keep `_ARCH_QUESTION`, add `_REQ` cues
  (requirement/scope/acceptance/user story). Precedence: REQ → PLAN → ARCH →
  DESIGN → **default `[IMPL]`** (was `[REQ]`). Skip lines already tagged with any
  of the 5. Document the tag→file map in the module docstring. Keep the existing
  path-containment guard and silent-skip-without-`ANTHROPIC_API_KEY` behavior.

### FSM (`src/pathly_orchestrator/`)
- `fsm_compose.py` — `build_prompt_for_agent`: add `feedback_file` param + the
  fix-mode block (3.1); role→artifact lookup.
- `fsm_ops.py` — pass `feedback["file"]` at the `build_prompt_for_agent` call
  (line 267).
- `fsm_ops_complete.py` — pass `feedback["file"]` at both calls (lines 93, 187).
- `fsm/engine_transitions.py` — `route_feedback`: honor optional
  `feedback_priority` (sort matched files); fallback = current dict order (1.5).
- `fsm/state.py` — extend flow-schema validation to accept `feedback_priority`
  (and confirm the new `feedback_routing` keys pass; roles must be in the known set).
- `db/queries/flow_graph_ops.py` — ensure `feedback_priority` survives the flow
  graph round-trip (it is a flow-level list, like `feedback_routing`).

### Skills (`src/pathly_data/core/skills/`)
- `team/review.md` — 5-way split in Phase 3 + routing section; builder hand-off.
- `team/test.md` — acceptance-vs-impl split; po hand-off.
- `fragments/feedback-protocol.md` — tag ⇄ file ⇄ role table + priority order.
- `agents/quality/reviewer.md`, `agents/quality/tester.md` — tag the violations.

### Studio (`studio/`) — optional, non-blocking
- The board already surfaces `feedback/*.md` (via
  `supervisor/artifact_reconcile.py`) and the routed role via `RunningEngine.role`.
  Optional polish: show the classification tag / routed role on the feedback card
  in the CommsPanel and the `FlowWizard` `Step6FeedbackRouting` editor so a human
  sees "routed to architect". Not required for the feature to work.

### Propagation (mandatory — adapter sync rule)
- `pathly-setup claude --apply --repair` (updates installed skills/agents/fragments)
  then `python -m build` (rebuilds codex/copilot/antigravity `_meta`). A core
  skill/agent/flow edit that skips this leaves the running agents stale.

---

## 5. Test plan

### Unit — classifier (`tests/test_hooks.py`)
- Each keyword family maps to its tag: "requirement"/"scope"→`[REQ]`,
  "phase"/"task DAG"→`[PLAN]`, "layer"/"dependency direction"→`[ARCH]`,
  "component"/"layout"→`[DESIGN]`.
- **Default is `[IMPL]`** for an untagged failure bullet (regression: today's
  default was `[REQ]`).
- Already-tagged lines (any of the 5) are left untouched (idempotent).
- Path-containment guard still rejects paths outside `features/`|`plans/`.

### Unit — routing (`tests/test_feedback_escalation.py` / new `test_fix_routing.py`)
- `ARCH_FEEDBACK.md` present → `target_agent == "architect"`; `PLAN_FEEDBACK.md`
  → `planner`; `DESIGN_FEEDBACK.md` → `designer`; `REQUIREMENT_GAP.md` → `po`.
- **Regression:** only `REVIEW_FAILURES.md` present → `builder` (byte-identical to
  today).
- **Priority:** `ARCH_FEEDBACK.md` + `REVIEW_FAILURES.md` both present → architect
  first (asserts `feedback_priority`/upstream-first).
- `build_prompt_for_agent(architect, path, feedback_file="ARCH_FEEDBACK.md")`
  contains the fix-mode block + `ARCHITECTURE_PROPOSAL.md`; builder path unchanged.

### Integration — drive the REAL FSM (`tests/test_runner_fsm_integration.py`)
Per the repo lesson (*drive the real FSM through ≥1 real transition; don't mock
both sides*):
1. Seed a `team` feature in `REVIEWING` with `feedback/ARCH_FEEDBACK.md`.
2. Call real `complete_stage` → assert `blocked`, `target_agent=="architect"`,
   `current_state` **still** `REVIEWING`, `decision=="block"`.
3. Remove `ARCH_FEEDBACK.md`, add `feedback/REVIEW_FAILURES.md`, `complete_stage`
   → `target_agent=="builder"`, still `REVIEWING`.
4. Remove all feedback → `complete_stage` → hits the `REVIEW.md` verify gate
   (`REVIEW_INCOMPLETE.md → reviewer`), then with a `RESULT: PASS` `REVIEW.md`
   advances `REVIEWING → TESTING`.
5. **Regression assertion:** a run whose only failure file is `REVIEW_FAILURES.md`
   produces the exact same sequence as before this feature.

---

## 6. Risks / open questions

1. **Default path must stay identical.** When every failure classifies `[IMPL]`,
   the reviewer writes only `REVIEW_FAILURES.md → builder`. The builder branch of
   `build_prompt_for_agent` and the loop are untouched. **Mitigation:** the
   regression assertions in §5 (unit + integration) gate this explicitly.
2. **Priority via dict order is fragile** across DB round-trip / `serializeFlow.ts`.
   **Mitigation:** the explicit `feedback_priority` list (1.5) + a serializer
   round-trip test.
3. **`classify_feedback` default flip `[REQ]`→`[IMPL]`** could mis-tag items in
   DESIGN-phase *question* files (where `[REQ]` was the sensible default).
   **Open question:** scope the default by filename (question files keep `[REQ]`
   default; failure files default `[IMPL]`), or accept `[IMPL]` globally? Lean:
   scope by file family. Note the hook is claude-only + best-effort, so it is a
   *fallback* — the reviewer's inline tags are authoritative.
4. **Agent compliance** — the reviewer may under-split (dump everything in
   `REVIEW_FAILURES.md`). **Mitigation:** that degrades safely to today's
   builder-only behavior; the split is an improvement, not a correctness
   dependency. The classifier hook backfills tags for visibility.
5. **Artifact-name drift** — `architect.md` says its output is `DESIGN_SPEC.md`,
   `artifact-manifest.yaml` says `ARCHITECTURE_PROPOSAL.md`; `po.md` writes
   `PO_NOTES.md` while the team pipeline keeps requirements in `USER_STORIES.md`.
   **Mitigation:** fix mode says "correct YOUR artifact, or the nearest equivalent
   (IMPLEMENTATION_PLAN.md / USER_STORIES.md)". **Open question:** unify the
   role→artifact names in a follow-up so fix mode can be exact.
6. **Loop bound** — an upstream role that writes a file re-routing to itself could
   loop. **Mitigation:** the supervisor caps at `MAX_FEEDBACK_ROUNDS` then
   escalates to human (`orchestrator_stage.py:170–176`); `escalation_routing`
   bumps a stuck file upstream by retry count.
7. **`build_prompt_for_agent` has no board context / pipeline history** (unlike
   `build_prompt`). A routed role fixes from the on-disk feedback + artifact only.
   Acceptable for a targeted patch; **open question:** whether to route fix-mode
   through the fragment-composing `build_prompt` path in a later iteration for
   board context.
8. **`reviewer.md` says "do not propose fixes."** Unchanged — the *reviewer* still
   only reports (into the right file); the *routed role* fixes. Clarify in the
   skill so the two contracts do not read as contradictory.
9. **Adapter sync** — forgetting `--repair` + `python -m build` ships stale skills
   to the running agents (the classic drift trap). Called out in §4.

---

## Appendix — resolution chain (multi-cause failure)

```
 reviewer (REVIEWING) finds 2 root causes, writes:
   feedback/ARCH_FEEDBACK.md      [ARCH]
   feedback/REVIEW_FAILURES.md    [IMPL]
        │
        ▼  route_feedback: highest priority open = ARCH_FEEDBACK
   architect (fix mode)
     ├─ patch ARCHITECTURE_PROPOSAL.md
     ├─ append [IMPL] item to REVIEW_FAILURES.md
     └─ delete ARCH_FEEDBACK.md
        │  supervisor force-deletes ARCH_FEEDBACK.md (resolved=[ARCH_FEEDBACK.md])
        ▼  route_feedback: only REVIEW_FAILURES open
   builder
     ├─ implement per updated proposal
     └─ delete REVIEW_FAILURES.md
        │
        ▼  route_feedback: none ─► REVIEWING→TESTING gate
   REVIEW.md missing ─► REVIEW_INCOMPLETE.md ─► reviewer re-reviews ─► RESULT: PASS ─► TESTING

 state = REVIEWING for the entire chain; no new state, no supervisor change.
```
