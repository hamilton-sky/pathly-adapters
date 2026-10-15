# Build the llm:operate tool loop in Electron main

Type: task
Status: resolved
Blocked by: 01, 02
Test first: yes (unit-test the loop logic with a stubbed model fn)

Extend `studio/src/main/ipc/llm.ts` (or a new `operate.ts` beside it)
with `llm:operate`:

- Input: `{message, board_id}`. Builds the prompt exactly like
  hq-copilot: ticket-01 operator system prompt + `<pathly-context>`
  packet (reuse the `GET /hq/context` packet builder via localhost
  HTTP, or share the assembler — don't reimplement) + user message.
- Tool definitions: exactly ticket 01's 6 tools as function schemas
  for node-llama-cpp's chat session. The model NEVER receives any
other tool. Unknown tool names in model output are rejected, never
executed (belt-and-braces).
- Loop: model emits tool call → if the tool is read-class, execute
  via localhost HTTP and feed the result back → if mutating, emit
  `operator:confirm {tool, args, plain_text}` over IPC and WAIT for
  `operator:resolve {approved: bool}` (ticket 04's UI answers it);
  on approval execute, on cancel skip with a note to the model →
  loop until the model answers or max 8 tool calls (small scope —
  this is not an agentic marathon).
- Streams `operator:token | operator:confirm | operator:done |
  operator:error` to the renderer. One automatic retry on API
  failure, then report the error plainly.
- Refusals: when the user asks for a refusal-list item
  (answer_question, directives, settings…), the system prompt covers
  it; ALSO hard-check the user message against the refusal patterns
  before invoking the model (same pattern-list approach as
  hq-copilot ticket 04) and reply with the redirect naming the right
  surface.

Unit-test the loop with a stubbed model function (no real model in
tests): confirm-gate ordering, unknown-tool rejection, max-calls cap,
refusal pre-check.

## Not in this ticket

- The picker UI + confirm cards: ticket 04. Audit log: ticket 05.

## Done when

- `pnpm --filter studio vitest run` passes for the new loop tests,
  covering: mutating call waits for resolve and executes only on
  approval; cancel → no HTTP call; unknown tool → rejected;
  9th tool call never happens (cap at 8); refusal-pattern message
  never reaches the model stub.
- `pnpm --filter studio typecheck` exits 0.

```check
$ pnpm --filter studio typecheck
exit 0
```

## Reference

- spec.md § Design, § Interfaces; ticket 01's Answer; ticket 02's
  tool→endpoint table
- `studio/src/main/ipc/llm.ts` (`llm:chat` handler — extend, don't fork)
- hq-copilot ticket 04 (refusal pattern-list approach)

## Answer

Resolved 2026-10-14. Built as **propose-only**, per ticket 01: the model's
function calls are recorded, never executed inside the turn, so the
confirm gate is the user's Run click on a card rather than an IPC pause in
the middle of generation. That also lets a card sit until the user decides
and be revalidated at the click (stale if the board changed).

- `studio/src/main/ipc/llmProposals.ts` (pure): `createProposalRecorder`
  (records offered calls, refuses unknown names, caps at 8 — the 9th call
  is answered "limit reached" and never becomes a proposal) and
  `recordingFunctions` (node-llama-cpp session functions whose handlers
  only record and tell the model it has NOT run).
- `llm:chat` takes `tools` and resolves `{proposals}` (preload +
  `global.d.ts` mirror it); `llm.ts` stays at 392 lines.
- The prompt is the server's: `POST /hq/prompt` with `enabled_actions`
  returns the operator turn (packet with short ids) + the tool specs —
  nothing reimplemented in Electron. The refusal pre-check is server-side
  (`hq_operator.operator_refusal_redirect`, before the packet or model).
- Renderer: `HQ/hqOperator.ts` (`askLocalTurn` → `askLlmWithTools` →
  proposals → `POST /hq/actions/check` → cards on the message) and
  `HQ/actionCards.ts` (Run → `POST /hq/actions/run`; Cancel = no request).
  `useHQ.tsx` swapped its calls in place and shrank 827 → 824 (baseline
  tightened).
- One automatic retry: deliberately none. The route's own refusal is the
  card's result; retrying a spawn could double-spend.

Tests: `llmProposals.test.ts` (offered set, order, unknown rejected,
9th never recorded, handlers only return text), `hqOperator.test.ts`
(read-only turn offers no tools and makes no action request; a proposal
becomes a checked card and never a run; Cancel makes no request; Run
executes via the server; stale; Studio-run approved → run → report; run
order). Refusal-before-model: `tests/local_operator/test_operator_turn.py`.
Both typechecks exit 0; Studio vitest 36 files / 238 tests green.
