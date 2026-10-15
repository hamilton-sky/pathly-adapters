# Map: hq-copilot

## Destination

HQ answers every message from a live, token-budgeted snapshot of the
Pathly boards: the free local model names real goals, runs, and pending
questions, refuses to act (pointing at the chief instead), and nothing in
the database changes as a result of asking. The Studio panel shows a
collapsible manifest of what context each answer was given.

**The bar.** `python -m pytest tests/hq_copilot/test_acceptance.py -q -p no:cacheprovider` passes: against a fixture board (2 goals, 1 running run, 1 pending agent question) the HQ prompt answers "what needs my attention?" naming the question and the run's stage, and a DB diff before/after proves zero writes.

## How to work this

- This repo is not feature-flow-installed: there is no `scripts/flow.py`.
  Work tickets in number order; take the lowest numbered open ticket whose
  blockers are resolved.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md`
  (append only). Status lives only in the ticket files; this map never
  repeats it.
- Ticket conventions mirror `pathly/features/chief-agent/tasks/` (Type,
  Status, Blocked by, Test first, Not in this ticket, Done when with a
  check block, Reference, Answer).

## Decisions so far

- 01 — packet order `attention` by default with user-selectable `progress` via `hq.packet_order`; budget 6000 tokens, chars/4 estimator (check runtime tokenizer as 2d); drop whole sections on overflow; system prompt and `<pathly-context>` delimiters approved as drafted; default HQ model Qwen3-8B (24 GB machine), Phi-4 Mini fallback. Settled with the user 2026-10-14.
- 01 — 2d finding: node-llama-cpp v3 in-process in Electron main exposes no token-count endpoint over IPC; chars/4 heuristic stands. Verified 2026-10-14.
- 02 — assembler built: `src/pathly_orchestrator/hq_context.py` (`assemble_packet(board_id, budget_tokens=6000, project_root=None)`; optional project_root scopes live runs, omitted → section cut as "no project_root"); strict priority truncation; 5s deadline; `HQContextUnavailable` on any failure, never a partial packet. 7 tests green; full regression (comms_board+db+http_api+hq_copilot) 895 passed, 2 skipped. Resolved 2026-10-14.
- 03 — `chat_agent.build_hq_prompt` (system prompt + packet + message; `[board context unavailable]` marker on failure) and `GET /hq/context` (`{packet, tokens_est, sections, budget}`; 400/404/503 semantics; new `blueprints/hq/` registered in `app.py`). Deviation: no server-side HQ model answer path exists to rewire (model is invoked Studio-side via `llm:chat`), so `build_hq_prompt` is the tested seam and Studio wires it in ticket 06. 12 tests green; regression 900 passed, 2 skipped. Resolved 2026-10-14.
- 04 — guardrails in `chat_agent.py`: `HQ_TOOL_SCHEMAS=()` + `_assert_no_hq_tools()` tripwire at the top of `build_hq_prompt`; `HQ_READONLY_REDIRECT` (ticket 01 text) + `hq_refusal_redirect` (verb+noun word-boundary patterns, `should I|we` carved out) + `prepare_hq_prompt` (build_hq_prompt's caller; redirect with zero model contact). Studio must call `prepare_hq_prompt` (ticket 06). 13 tests green; regression 913 passed, 2 skipped. Resolved 2026-10-14.
- 05 — settings (`db/queries/hq_settings.py`, re-exported from `app_settings.py`): `hq.default_model`=`qwen3-8b` (Done-when's phi-4-mini line was stale; ticket 01 settlement wins), `hq.context_budget_tokens`=6000, `hq.packet_order`; new `hq_models.py` (context-window table, `hq_eligible` fail-closed); Studio: qwen3-8b registered, per-caller `maxTokens` on `llm:chat` (default 512); `GET /hq/context` reports `model`/`eligible_model`. Closed the runtime open question: Studio declares no context limits; node-llama-cpp v3 in Electron main. 6 tests green; regression 918 passed, 2 skipped. Resolved 2026-10-14.
- 06 — Studio manifest (TSX): `Message.contextManifest` in chatStore; new `HQ/ContextManifest/` (collapsible line, token bar, section rows, eligible_model warning, amber unavailable note mirroring the panel's toolBar); MessageList renders it under local-model answers + renders the `[board context unavailable]` marker as the amber note; useHQ fetches `GET /hq/context` after each local answer (awaited before setLoading(false)). Prompt pipeline untouched per ticket. Parse-checked + 7 vitest green; `pnpm typecheck` + manual Studio check still need the Mac. `pnpm typecheck` (from `studio/`) exits 0 on the Mac 2026-10-14 (pnpm v11 needed `approve-builds`; new `studio/pnpm-workspace.yaml` with allowBuilds). Claimed 2026-10-14.
- 07 — acceptance: `tests/hq_copilot/test_acceptance.py` (3 tests: prompt carries question + BUILDING stage + 3/5 tasks; DB snapshot diff empty across the full HQ path; redirect with zero model calls). `build_hq_prompt`/`prepare_hq_prompt` gained optional `project_root`. Full per-ticket command: 921 passed, 2 skipped (caught + fixed a stub regression from the signature change). Manual Studio check pending the Mac. Claimed 2026-10-14.
- Review 2026-10-14 — wired end to end: `hq_prompt.py` (moved out of `chat_agent.py`) + `POST /hq/prompt`; Studio sends the server-built turn and attaches its manifest before streaming; `num_ctx`/min context from `hq_models.hq_required_context`; option-object crash fixed; refusal redirect matches imperatives only; qwen3-8b selectable. Manual Studio check pending a downloaded model.
- Review 2026-10-14 — real model verified: Qwen3 8B answers real boards from the packet in 16–23 s (no factual hallucination); thought budget 768 / maxTokens 2048, context exactly 16k; fixed Phi-4 Mini URI (401) and the `hf_*` download filename that made every built-in download unloadable; Qwen3 8B is now Studio's default model.
- Review 2026-10-14 (round 3) — HQ panel: status strip, /PATHLY chips and the permanent FSM menu card removed; context checkboxes on the latest answer (`sections` on POST /hq/prompt; opt-in `summaries` section = artifact AI summaries); board name on the context line; HQ answers about the board open in the Command Center (not the runner topic, which can be a goal slug); Fast (no reasoning, ~2 s) / Deep (reasoning streamed into ThinkingBlock) for the built-in model; answers rendered as escaped Markdown (lib/safeMarkdown); chat history saved per project (switching projects swaps the chat); New chat stops an answer in flight. Designer recommendation (not built yet): move context + action selection to a chip row above the HQ input with one shared popover.
- 06/07 — resolved 2026-10-14 after the in-app check. Composer chip row built: the Context tab replaces the answer's checkboxes (answers keep a read-only line + "Adjust for next question"); the manifest reports per-section `tokens` for the shared meter; MiniLM status moved into the model popover; `resolveHqBoard`'s open-topic fallback must name a known feature board. Actions tab: pathly/features/local-operator.

## Open questions

- Which local runtime serves the models Studio downloads (llama.cpp
  server? something else?) — ticket 05 reads the Studio code and records
  the answer; the eligibility check must match the runtime's real context
  limits.
- Exact token estimator for the budget (chars/4 heuristic vs the
  runtime's tokenizer) — ticket 01 decides; heuristic is the default
  unless the runtime exposes a cheap count endpoint.
