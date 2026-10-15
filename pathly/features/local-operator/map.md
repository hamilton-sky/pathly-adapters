# Map: local-operator

> Renamed from `local-worker-adapter` 2026-10-14: the local model is
> not a planner worker — it is a small operator driving Pathly's API.
> Old tickets 01–08 are superseded by the tickets below.

## Destination

HQ has an **Operator (local)** mode: the free local model answers
simple board questions (reusing hq-copilot's packet) and invokes 6
bounded API tools — spawn_planner, start_run, pause_run, resume_run,
retry_stage, post_message. Every mutating action is proposed in the
chat and executes only after the user hits Run. Heavy work (planning,
building) always runs on cloud headless CLIs spawned through the API;
the operator never composes, never touches directives, questions,
settings, files, or shell. Every executed action is audit-logged as
`local-operator`.

**The bar.** `python -m pytest tests/local_operator/test_acceptance.py -q -p no:cacheprovider` passes: with a stubbed model, "rerun the failed test stage" yields a confirmation proposal and — after confirmation — exactly one `retry_stage` API call; without confirmation nothing is called; the forbidden tools are never in the offered schema.

## How to work this

- This repo is not feature-flow-installed: there is no `scripts/flow.py`.
  Work tickets in number order; take the lowest numbered open ticket whose
  blockers are resolved.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md`
  (append only). Status lives only in the ticket files; this map never
  repeats it.
- Related: `pathly/features/hq-copilot/` (board packet, ticket 01
  settled 2026-10-14); `pathly/features/chief-agent/` (the chief
  remains the full operator — this feature is the small one).

## Decisions so far

- 2026-10-14 — pivot: local model is a small API operator, not a planner worker; tool loop lives in Electron main (`llm.ts` extension), not a Python/Ollama harness; 6-tool surface; per-action confirmation.
- 01 — settled with the user 2026-10-14: curated 9-action catalog (pause/resume/retry/stop_run, run_goal, plan_goal, post_note, diagram_artifact, add_diagram_to_board); Settings chooses which HQ may use (server `hq.actions.available`, default run control + post_note), the composer ticks up to 8; propose-only model calls, execution at the click; diagrams run in Studio; built-in runtime only. Ticket 04's picker mode is replaced by the composer Actions tab.
- 02 — no wrappers: server actions dispatch in-process to the real routes (`blueprints/hq/_action_exec.py`); new `/hq/actions` (catalog, availability), `/hq/actions/check|run|report`; fingerprints make a changed board's card stale. 20 mapping tests green.
- 03 — propose-only loop: `llm:chat` `tools` → record-only node-llama-cpp functions (`main/ipc/llmProposals.ts`), proposals → `/hq/actions/check` → cards; no retry loop (the route's refusal is the result).
- 04 — superseded by the composer Actions tab + confirm cards + Settings → Intelligence → HQ actions (no picker mode, no input lock).
- 05 — audit = one `local-operator` status post on the HQ board per executed action, server-stamped.

## Open questions

- Exact existing endpoints for the 6 tools — ticket 02 verifies each
  and names any thin wrapper needed.
