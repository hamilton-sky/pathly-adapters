# Architect Assessment

## Verdict

This is a strong feature direction. It fixes a real architectural fracture: Pathly currently has one spawn substrate but multiple prompt-composition contracts above it, which is why behavior and result handling drifted across Summary, Analyze, Split, Decompose, and goal execution.

The proposed answer is correct at the boundary level: keep execution ownership where it already lives, but make prompt assembly and Pathly wiring declarative and shared.

## What Is Strong

### One Primitive, Context As The Switch

The orchestration reframe is the right one. Treating `goal_id` presence as the "on a goal" switch and selecting a composition profile from that context is simpler and more durable than arguing about which surface is canonical.

### File Capture As The Stable Output Contract

Promoting file-based capture from an editor-specific trick into the common transform contract is the best part of the design. It is adapter-agnostic, already proven locally, and removes the brittle stdout-tail parsing path that caused summary corruption.

### Server-Side Composition

Keeping composition on the server is the correct call. The manifest is DB-overridable, adapter-cap gating lives in Python, and fragment bodies already live there. A TypeScript mirror would create a second truth source and guaranteed drift.

### Conservative Loop Scope

The choice to convert only the board-I/O surface for `drain-dag` and the frontier loop is disciplined. Polling loops are not one-shot stage agents, so forcing one-shot fragments onto them would blur lifecycle semantics and create false completion behavior.

## Main Risks

### Profile Selection Can Become Implicit Magic

Using `goal_id` as the selector is good, but only if the spawn context becomes explicit and inspectable everywhere. If profile resolution stays partly manifest-driven and partly hidden in call-site behavior, this will be harder to debug than the current duplication.

### Two Partial Composition APIs

The design intentionally uses HTTP composition for renderer-owned actions and in-process composition for supervisor-owned actions. That split is acceptable, but it means the team must guard against subtle divergence in variable injection, dash-safety, and fallback behavior.

### UX Consistency Depends On Error Normalization

The architecture is only half done if `ERROR:` file outputs are not normalized into the same pill/error path everywhere. Without that, the new capture contract will still feel inconsistent even if the prompts are unified.

### P1 Scope Creep

P1 combines decompose conversion, loop board-I/O conversion, the `profiles:` refactor, and cleanup of raw consultation skills. That is too much for one slice if the goal is low-risk rollout. The profile refactor in particular changes the composition model, not just feature coverage.

## Sequencing Advice

### Ship The Seam Before The Taxonomy Refactor

`POST /skills/compose`, the two transform fragments, and Summary/Analyze/Split conversion are the right first milestone. That delivers user-visible value and proves the seam before changing manifest vocabulary.

### Delay `blocks:` To `profiles:` Until After P1 Usage Proves Out

The naming model is good, but the refactor should follow successful use of the new fragments in both standalone and goal-backed flows. Renaming too early increases migration risk without changing behavior.

### Treat Decompose As The First Goal-Backed Proof

Decompose is the right first board-backed consumer because it is narrow and already conceptually close to declarative task posting. If that works cleanly, then loop board-I/O conversion is much safer.

## Recommendation

Proceed with the feature.

I would approve it with one constraint: keep the rollout in three hard gates.

### Gate 1

P0 seam plus transform conversion only.

### Gate 2

Decompose plus the two new board fragments, with no manifest taxonomy rename yet.

### Gate 3

Loop/drain board-I/O extraction and only then the `profiles:` vocabulary cleanup if the first two gates validate the model.
