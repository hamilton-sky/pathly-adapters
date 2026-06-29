# PO Notes — unified-cli-composition

_Last updated: 2026-06-29_

## Who Is This For

The primary user is the **Pathly engineering maintainer** — the developer who builds, extends, and debugs Pathly Studio workflows. The secondary audience is any Studio user who relies on Summary, Analyze, Split, Decompose, and goal-run execution and currently sees inconsistent behavior (codex chrome leaking into summaries, stdout truncation, different result-capture paths per action). This feature is an internal coherence fix with direct user-visible side effects: Summary quality improves, behavior stops varying by engine.

## Definition of Success

Every CLI-engine invocation in Pathly assembles its prompt through the same `compose_skill` primitive — skill body + gated fragments selected by context — with no bespoke per-call-site prompt construction. The three P0 signals are:
1. Summary works correctly with both claude and codex (no chrome leakage, no stdout truncation) because results flow through file-based capture rather than a PTY stdout tail.
2. Analyze and Split already use file-based capture and continue to do so — now as canonical implementations of a shared fragment contract, not one-offs.
3. A developer can add or change a fragment for any of these actions by editing the manifest, not by touching five separate call sites.

## Out of Scope

- **Loop executor board-I/O** (drain-dag, `_run_loop` frontier): only the board-I/O surface gets converted at Gate 2; the loop body stays supervisor-Python-only.
- **`blocks:` → `profiles:` manifest vocabulary rename**: deferred to Gate 3 after P0+P1 prove the model. Renaming before usage is validated adds migration risk with no behavior change.
- **Model/Brightsky/websocket split**: separate deferred plan; must not be entangled with this work.
- **Raw board skills `team/architect`, `team/research`**: P3.
- **`agent-output-redirect` fragment**: P3.
- **Pure transforms posting to the board by default**: a standalone Analyze/Split/Summary with no `goal_id` does NOT post to the board. Board posting is gated on goal-backed context (`goal_id` present). If a future decision changes this, it is an explicit scope expansion, not an assumption.
- **TypeScript mirror of `compose_skill`**: ruled out. Server-side composition is the only implementation.

## Constraints

1. **Three hard rollout gates** (architect-mandated, non-negotiable):
   - Gate 1: `POST /skills/compose` seam + `client-file-output` + `artifact-transform` fragments + Summary/Analyze/Split conversion only.
   - Gate 2: Decompose conversion + `board-start-context` + `task-dag-post` fragments. No manifest vocabulary rename.
   - Gate 3: Loop/drain board-I/O extraction + `profiles:` rename if Gate 1+2 validated the model.
2. **Profile selection must be inspectable**: `goal_id`, `executor`, and `kind` must be explicit in the spawn context object — no implicit resolution from call-site behavior.
3. **Error normalization is P0-blocking**: `ERROR:` file outputs must flow through the same pill/error path everywhere before the new capture contract ships. Silent divergence in error handling would make the new path feel as inconsistent as the old one.
4. **Dash-safety applies to all composed prompts**: any prompt delivered via CLI argv must pass through `_dash_safe_prompt` / `dashSafePrompt` — this is already enforced in three places and must not regress.
5. **Visibility is constant**: every CLI-engine spawn opens a visible PTY tab. The headless/interactive split is a driver knob (who drives the loop), not a visibility toggle.
6. **Decompose is the first goal-backed proof** (architect recommendation): if Decompose conversion at Gate 2 works cleanly, loop board-I/O conversion is much safer. Do not attempt Gate 3 before Gate 2 succeeds.

## Open Questions

1. **Transforms and board discoverability**: should a standalone transform (no `goal_id`) post an `artifact` to the board after writing its output file, so its result is catalog-indexed and findable by other agents?
   - _Working assumption_: No. Pure transforms compose `client-file-output` + `artifact-transform` only. Board posting (`comms-post`) is gated on `goal_id` presence. Accepting this keeps the standalone profile clean and avoids board noise for editor-level one-shots.

2. **Client action progress surface**: for a goal-backed client action, should progress surface as a board `status` post, as an in-place `ActionPill`/`RunPill`, or both?
   - _Working assumption_: `ActionPill`/`RunPill` is the primary feedback layer; board `status` posts happen for goal-backed actions only, consistent with how board-run agents work today.

3. **P1 scope boundary**: should the `profiles:` manifest refactor be bundled with Gate 2 (Decompose conversion) or held strictly for Gate 3?
   - _Working assumption_: Gate 3 only. The vocabulary change does not affect behavior; delaying it reduces Gate 2 risk.

4. **Error normalization timing**: does error normalization (shared `ERROR:` file → pill/error path) ship as part of Gate 1, or can it follow in a fast-follow commit?
   - _Working assumption_: Gate 1 includes at least the contract definition (what an `ERROR:` file looks like); the UI normalization that renders it can be a Gate 1 fast-follow if it does not block the seam.
