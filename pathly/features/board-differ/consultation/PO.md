# Board Differ — PO Consultation

_Product Owner review of `pathly/features/board-differ/APPROACH.md`, 2026-07-06._

## Verdict
**Reshape, then build a narrow slice** — build surface (a) **with the Impact panel as one MVP**, kill the (a)-alone milestone. The plain diff was cut for redundancy last month for a good reason; it's the *impact* half that justifies revival.

## User value
The user is **the human supervisor** driving a headless run from the board. The job-to-be-done at the moment this feature fires: an agent run just posted an artifact claiming "I changed `build_block`," and the supervisor must decide **continue / block / escalate** *without having watched the agent work*. That's the whole premise of headless supervision — the board is the only place trust gets established.

So the job is **"let me vet a change I didn't watch happen, fast enough that I'm not tempted to rubber-stamp the summary."** Real pain, specific to this product.

The sharp part: **surface (a) alone does not do that job.** A plain artifact-vs-HEAD diff is exactly what `change-explorer` / `DraftDiffViewer` already gave — *why it was cut in June for redundancy*. The genuinely new thing is **"accepting this touches these 3 callers and the runner-prompt flow — intended?"** That blast-radius reframing is the entire reason to spend cycles here. If the Impact panel slips to "phase 2," the phase-1 ship is redundant-by-definition and a reviewer would (correctly) cut it again.

**The value is crisp only when diff + impact ship together. The diff is the substrate; the impact is the product.**

## MVP slice
**Artifact card → "See changes" → read-only diff (reused `CodeDiffView`) + Impact panel, for a single code file, against committed HEAD.**

In scope: one artifact, one code file, split/unified read-only diff; Impact panel calling `/code/query op:"impact"` → callers + affected flows; graceful degradation (graph off / non-code → plain diff, panel absent).

**Do not cut a release between (a) and the Impact panel.** The releasable unit is (a)+impact. Internally build the diff first (impact depends on it), but frame the roadmap so nobody ships the redundant half and declares victory.

**NOT the MVP:** surfaces (b) draft-triage and (c) two-artifact compare — real cost, not required to prove the core loop. Fast-follows *if* the MVP earns its keep.

## User stories + acceptance criteria
- **US-1 See what a run changed, from the card** — "See changes" action on a code artifact card → read-only split/unified diff of artifact vs `git show HEAD:<path>`; no accept/reject/apply controls.
- **US-2 See the blast radius (the differentiator)** — Impact panel beside the diff lists changed symbols, affected callers, affected flow(s), from `/code/query op:"impact"`; framing is blast-radius, not a symbol dump.
- **US-3 Graceful degradation** — graph off → plain diff, panel absent (not an error); non-code artifact → text diff only; impact failure never 500s or blocks the diff.
- **US-4 Trust the baseline** — the view states its baseline (committed HEAD) visibly; artifact == HEAD → "no changes," not an empty/ambiguous diff.
- **US-5 Act on what I saw** — closing the view returns to the board with the run's continue/block/escalate controls intact (v1 may reuse existing controls; the loop must be unbroken).

## Scope risks / out-of-scope
Balloon risks: turning the read-only viewer into an editor (surface b apply); impact-panel richness (call-graph, click-to-jump); multi-commit baselines; markdown-aware impact.

Explicitly OUT for v1: surface (b) apply, surface (c) compare + picker, any write/mutation from the diff, clickable/navigable impact graph, configurable baselines.

## Open product questions
1. **Redundancy audit (decisive):** confirm `change-explorer`/`DraftDiffViewer` don't already surface impact — if they do, this collapses to "add an Impact panel to the existing viewer."
2. **Does the impact reframing actually change supervisor behavior?** Cheapest test: dogfood the MVP on one real headless run and check whether the panel ever changed a continue→block decision.
3. **How often does a run's artifact map cleanly to one code file at HEAD?** MVP assumes one artifact ↔ one file ↔ clean HEAD baseline.
4. **`detect_changes` contract** — implementation-feasibility question for the architect, not a product blocker.

**Priority call:** build **now, but only in the reshaped form** — (a)+impact as one ship, one file, read-only. In the spec's literal (a)-alone-first form, defer it.
