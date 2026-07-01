# HQ Panel — Retrospective

## Cost Summary
Total: $0.77

| Agent   | Model              | Tokens in | Tokens out | Total   | Tool uses | Wall    | Cost     | % of total |
|---------|--------------------|-----------|------------|---------|-----------|---------|----------|------------|
| builder | claude-sonnet-4-6  | 51,254    | 12,814     | 64,068  | 52        | 765s    | $0.3460  | 45%        |
| builder | claude-sonnet-4-6  | 31,888    | 7,972      | 39,860  | 26        | 153s    | $0.2152  | 28%        |
| builder | claude-sonnet-4-6  | 30,636    | 7,659      | 38,295  | 21        | 141s    | $0.2068  | 27%        |

> The third builder spawn is the test-fix cycle (conv=0). All cost was builder — no separate reviewer or tester agent was spawned (both ran inline in the parent session).
>
> Use this to decide: was standard rigor worth the cost? Would lite have been enough?

---

## Plan Quality

**Conversation sizing:** Conv 1 was too big. Phases 0–3 packed a folder rename, a new Zustand store, and three new component trees (FlowControlBar + two sub-components + StageStatusStrip) into one 64K-token conversation. The scope overload produced 9 review violations that a narrower prompt would have avoided. Conv 2 was well-scoped — three focused behaviors, half the tokens.

**Surprises:**
1. **Runner button bodies were empty** — the plan said "POST to /runner/start" but never specified the body shape. All buttons sent `{}` until we read `http_server.py` live and discovered the full schema.
2. **`choice` vs `decision` field** — plan said POST to `/runner/decision` but didn't name the payload field. Builder guessed `choice`; server expected `decision`.
3. **Stale server process** — the running process on port 8765 was an old version without runner routes. No plan step existed for verifying the running server version matches the source.
4. **GATE_FAILED: missing REVIEW.md artifact** — the FSM blocked REVIEWING→TESTING because the reviewer didn't write the required REVIEW.md artifact. The plan listed REVIEW.md as a pipeline file but didn't specify it as a reviewer exit contract.

**Missing from plan:** A table of every runner endpoint with its exact POST body schema. "Buttons call `/runner/X`" is not sufficient — the contract is the body shape, and every body was either wrong or empty until discovered at runtime.

---

## What Worked

- Two-conversation split (structural Conv 1 / behavioral Conv 2) was a good architecture — code could typecheck after each.
- Zustand store design was clean and extensible — `setRunnerState` partial update pattern needed no rework.
- SSE reconnect backoff (3s fixed, then 3s × 2^n capped 30s) worked first time and held up under testing.
- `RunnerBtn` extraction — wrapping Tooltip+button into a helper made FlowControlBar compact and consistent.
- `getState()` in async event handlers — using `useRunnerStore.getState()` inside `postAction` avoided stale closure bugs without needing extra useCallback wrappers.

---

## What to Improve Next Time

- **Specify POST body schemas in the plan** — every endpoint entry in CONVERSATION_PROMPTS.md must include a `body:` example object, not just the URL.
- **Split Conv 1 by concern** — rename as its own conversation (1 file category), store as another, components as a third. Each is under 30K tokens and produces a clean typecheck gate.
- **Add server version check to Phase 0** — pre-flight should curl `/health` and compare the `version` field against `pyproject.toml`. A mismatch is a hard stop.
- **Reviewer exit contract must be explicit** — CONVERSATION_PROMPTS.md should say "write pathly/plans/\<feature\>/REVIEW.md summarising round + verdict" as the first item in the reviewer's done criteria.
- **Name payload fields explicitly** — when a plan says "POST to /runner/decision", it must say "body: `{ topic, decision }`" not just the URL.

---

## Seed for Next Storm

> Paste this block as context when starting the next related storm session:

The hq-panel feature delivered a working HQ Pipeline Control panel with runner buttons (Start/Pause/Resume/Advance/Reroute/Retry/Abort), SSE-driven live state (stage, cost, session), and decision-menu round-trips. The main lesson: plan files must include the exact POST body schema for every API endpoint — URL alone is insufficient. Conv 1 was too wide (rename + store + 3 component trees in one shot); future panels should split structural and behavioral work across more conversations with a typecheck gate after each. Total build cost: $0.77 across 3 builder spawns.
