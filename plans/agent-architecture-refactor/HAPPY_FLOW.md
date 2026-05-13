# agent-architecture-refactor — Happy Flow

## End-to-end scenario: pipeline stage spawning scout context

**Before this feature:**

A builder in the pipeline reaches a point where it needs codebase context. It calls `scout-path` as a sub-skill. `scout-path` parses the NEEDS_CONTEXT block and spawns scout agents. Results return through two indirection layers before the builder can continue. The full `scout-path.md` skill definition is loaded into the builder's context window.

**After this feature:**

1. A builder reaches a point where it needs codebase context.
2. It outputs a `## NEEDS_CONTEXT` block.
3. The orchestrating skill (build.md / team/build.md) reads the block and spawns a `scout` agent directly with `ROLE: builder`, `scope`, and `question` parameters.
4. The scout returns findings.
5. The skill injects findings as `## Scout Findings` and proceeds to the main build phase.
6. No `scout-path` indirection. No skill-in-skill. Clean context.

---

## End-to-end scenario: tester gathering test context

1. Tester is spawned with `phase: analyze`.
2. Tester outputs a `## NEEDS_CONTEXT` block identifying test files and fixtures to examine.
3. The orchestrating skill reads the block and spawns a `scout` agent (declared in tester.yaml `can_spawn`).
4. Scout returns findings about test infrastructure.
5. Tester is re-spawned with `phase: test` and `## Test Context` injected.
6. Tester verifies all acceptance criteria against real test infrastructure — no guessing, no missing fixtures.

---

## End-to-end scenario: user runs /team feature

1. User types `/team my-feature standard`.
2. `team.md` parses arguments: FEATURE=my-feature, rigor=standard.
3. `team.md` detects the feature (found `plans/my-feature/STATE.json`).
4. `team.md` asks mode selection (auto-flow or manual). User replies "1".
5. `team.md` spawns the `orchestrator` agent with FEATURE=my-feature, rigor=standard, autoFlow=true, entryStage=discovery.
6. Orchestrator recovers FSM state from disk (STATE.json says BUILDING).
7. Orchestrator routes to `team/build` sub-skill.
8. Build completes. Orchestrator handles the BUILDING → REVIEWING git commit.
9. Orchestrator routes to `team/review` sub-skill.
10. Review passes. Orchestrator updates PROGRESS.md, commits with chore message.
11. Orchestrator routes to next build conversation or to TESTING when all done.
12. Each stage runs in the orchestrator's context — no accumulation in team.md's session.
