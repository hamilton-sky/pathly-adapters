# PO Notes — board-differ

_Last updated: 2026-07-15_

## Who Is This For

The **human supervisor** driving a headless multi-agent run from the Pathly Command Center board.
This person has not watched the agent work — the board is their only trust surface. At the moment
this feature fires, an agent has just posted an artifact claiming it changed code, and the
supervisor must decide **continue / block / escalate** without having witnessed the work. The
job-to-be-done is: "let me vet a change I didn't watch happen, fast enough that I'm not tempted
to rubber-stamp the agent's summary."

## Definition of Success

The feature succeeds when a supervisor can open a run's artifact card, see the exact lines the
agent changed against committed HEAD, and see the **blast-radius** — which callers and execution
flows that change touches — all without leaving the board. The specific outcome that matters: the
supervisor can make an informed **continue vs. block** decision based on real impact, not just the
agent's self-reported summary.

**Do not cut a release between the plain diff and the Impact panel.** The releasable unit is
surface (a) + Impact panel shipped together as one MVP. The plain diff alone is redundant with
already-cut tooling (`change-explorer`/`DraftDiffViewer`) and has no product justification
without impact context. Internally, build the diff first (impact depends on it), but the
shippable milestone is diff + impact.

## Out of Scope

**For the MVP (v1):**
- Surface (b) — draft-triage with accept/reject/apply controls (real cost, not needed to prove the core loop)
- Surface (c) — two-artifact compare with a file picker
- Any write/mutation from the diff view
- Clickable/navigable impact graph (call-graph visualisation)
- Multi-commit baselines (default is committed HEAD; revisit if runs span multiple commits)
- Markdown-aware or hunk-level hypothetical impact (the `detect_changes` tool operates on the working-tree vs HEAD, whole-repo — per-hunk impact requires new engine work out of scope here)
- The Walkthrough artifact (single-agent graph-fed narrative) — proposed as step 5 in the rollout, not the MVP
- Walkthrough export to `.html` — step 6, fast-follow after native walkthrough

**Out permanently (v1):**
The Impact panel must not claim per-hunk or hypothetical impact the tool cannot give. The honest
framing is "impact of current uncommitted changes in this file" — filter `detect_changes(project)`
output to the diffed artifact's path. No synthetic-diff support.

## Constraints

1. **`detect_changes` is not yet implemented** in the backend — `op:"impact"` today routes to the
   same `query_graph` path as `op:"callers"` and returns a symbol/caller-count structure block, not
   a `detect_changes` result. Building the real impact panel requires: a new `CliProvider.detect_changes(project)`
   method (`runner/code_context_cli.py`), a routing branch in `code_query` (`blueprints/code/query.py`)
   that sends `op:"impact"` there and filters by file, and a parse/filter step (~60–100 LOC total,
   not ~20). This is a hard technical dependency the architect has verified.

2. **No git baseline in the app today** — surface (a) requires a new main-process IPC (`git show HEAD:<path>`)
   that does not exist. `fs:read` is the only file bridge; `simple-git` is not currently exposed. New untracked
   artifacts must fall back to an "all-additions" diff, not an error.

3. **`useDraftDiff`/`CodeDiffView` use section-level markdown diff, not line-level code diff** — reusing
   them for code files fights their grain. A separate code-hunk diff path is needed for surface (a); the
   existing component is the correct fit for surface (b) draft-triage.

4. **Layer rule must be respected:** `detect_changes` shelling out must happen in `runner/code_context_cli.py`
   (not in the HTTP handler), routing branch in `blueprints/code/query.py`. The `http_server → runner`
   dependency direction is an architecture constraint.

5. **`DraftDiffViewer` redundancy pre-build check (open):** before building, confirm
   `change-explorer`/`DraftDiffViewer` do not already surface an Impact panel. If they do, this
   collapses to "add ImpactPanel to the existing viewer." The board decision from consultation
   requires this audit to happen at the start of build, not blocked on it.

6. **Graceful degradation is a hard requirement, not a nice-to-have:** graph off / non-code artifact /
   `detect_changes` failure must never 500 or block the diff. The diff view must degrade cleanly (Impact
   panel absent, not errored).

## Open Questions

1. **Baseline for surface (a):** committed HEAD vs. run-start commit. If a team-mode run spans multiple
   commits, HEAD-vs-artifact understates the run's change. Working assumption: committed HEAD for v1; revisit
   if team-mode runs regularly span multiple commits. Consider persisting a run-start SHA in the board run record.

2. **Does the impact reframing actually change supervisor behavior?** Cheapest validation: dogfood the MVP on
   one real headless run and check whether the panel ever changed a continue→block decision. This is a post-ship
   learning loop, not a pre-ship gate.

3. **How often does a run's artifact map cleanly to one code file at HEAD?** The MVP assumes one artifact ↔
   one file ↔ clean HEAD baseline. Working assumption: frequent enough in the primary use case (agent touches one
   file, posts it as an artifact); fall back to "multiple files" UX in surface (d) (multi-file run-review panel,
   already agreed as a fast-follow in board governance).

4. **Surface (d) timing** (multi-file run-review panel, "Review changes" from a run card): already agreed in
   board governance as a fast-follow after the MVP. Not a blocker — include in the roadmap note in the plan.
