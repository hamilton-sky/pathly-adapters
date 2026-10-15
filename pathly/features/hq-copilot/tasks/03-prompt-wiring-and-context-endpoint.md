# Wire prompt assembly into chat_agent.py and expose GET /hq/context

Type: task
Status: resolved
Blocked by: 01, 02
Test first: yes

Make every HQ message carry the board snapshot:

1. `chat_agent.py` gains `build_hq_prompt(user_message, board_id) -> str`:
   ticket 01's fixed system prompt + the `<pathly-context>` packet from
   `hq_context.assemble_packet` + the user message. On
   `HQContextUnavailable` it returns the system prompt + user message
   plus a literal `\n\n[board context unavailable]` marker (the Studio
   panel renders this visibly; never a silent bare answer).
2. The existing HQ answer path calls `build_hq_prompt` instead of
   sending the bare message. No other `chat_agent.py` caller changes
   behavior.
3. New route `GET /hq/context?board=<id>` returning `{packet,
   tokens_est, sections: [{name, included, cut_reason}], budget}` from
   the same assembler (the Studio manifest in ticket 06 reads this; it
   is also the debugging surface). Unknown board → 404, never an empty
   200.

The local model invocation itself is untouched: same runtime, same
parameters, still no tools (guardrails are ticket 04).

## Not in this ticket

- Read-only refusal behavior: ticket 04 owns the system prompt's refusal
  semantics and tests them.
- The Studio manifest UI: ticket 06.

## Done when

- `python -m pytest tests/hq_copilot/test_prompt_wiring.py -q -p no:cacheprovider` passes and covers: `build_hq_prompt` output contains the system prompt, the delimited packet, and the user message in that order; on a forced assembler failure the output contains `[board context unavailable]`; `GET /hq/context` returns the packet shape with section statuses for a known board and 404 for an unknown one; existing `chat_agent` tests still pass unchanged.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/hq_copilot/test_prompt_wiring.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Design, § Interfaces; ticket 01's Answer; ticket 02's
  `hq_context.assemble_packet`
- `src/pathly_orchestrator/chat_agent.py` (read-only)
- `src/pathly_orchestrator/http_server/blueprints/` (route registration pattern)

## Answer

Implemented 2026-10-14.

1. `chat_agent.py` gains `HQ_SYSTEM_PROMPT` (ticket 01's fixed prompt,
   verbatim) and `build_hq_prompt(user_message, board_id) -> str`:
   system prompt + `<pathly-context>` packet + user message, in that
   order; on `HQContextUnavailable` the packet is replaced with a
   literal `\n\n[board context unavailable]` marker. Lazy import of
   `hq_context` — no new import cycle (`chat_agent` is imported at
   module level by `blueprints/ops/chat.py`).
2. **Deviation, point 2 of the ticket:** there is no existing HQ model
   answer path in `chat_agent.py` to rewire — the module serves
   `POST /chat` (Conductor panel) with heuristic replies, and the real
   HQ model invocation happens Studio-side via `llm:chat` IPC. Wiring
   `build_hq_prompt` into `handle_chat`'s `pathly_chat` branch would
   change existing Conductor behavior (forbidden by the ticket) without
   reaching any model. So `build_hq_prompt` stands as the canonical
   tested seam; the Studio HQ panel calls it (via the packet endpoint
   below) in ticket 06. No other `chat_agent.py` caller changes
   behavior — verified by the unchanged `tests/http_api` suite.
3. New blueprint `http_server/blueprints/hq/` (`context.py` +
   `__init__.py`, registered in `app.py` following the
   comms/control `all_blueprints` pattern): `GET /hq/context` returns
   `{packet, tokens_est, sections: [{name, included, cut_reason}],
   budget}`. `?board=` required (400 without); unknown board → 404
   (known = the scope has any messages or any runs — an empty-but-known
   board still 200s with its empty packet); optional `?project_root=`
   scopes the live-runs section; assembler failure → 503.

Tests: `tests/hq_copilot/test_prompt_wiring.py` (5 tests) + the 7
assembler tests — 12 passed. `check_file_size.py` exits 0. Full
regression (`tests/comms_board tests/db tests/http_api
tests/hq_copilot`): 900 passed, 2 skipped, 2026-10-14 (clean clone at
the Mac's commit era, venv on the assistant's machine).

### Review follow-up 2026-10-14 — the seam is now reachable

The Answer above left `build_hq_prompt` as a Python seam with no caller:
Studio cannot call Python, so the model kept receiving the bare message
while the manifest described a packet it never saw. Closed:

- HQ prompt code moved out of `chat_agent.py` (the Conductor `/chat`
  handler — reverted to HEAD) into `src/pathly_orchestrator/hq_prompt.py`
  beside `hq_context`/`hq_models`. `build_hq_turn` returns the system
  prompt and the user turn separately (both runtimes take a separate
  system prompt); `build_hq_prompt` is its one-string form, byte-identical
  to before.
- New `POST /hq/prompt` (`blueprints/hq/prompt.py`): `{message, board,
  project_root?, model?}` → `{redirect | system_prompt + prompt, manifest,
  context_tokens}`. Unknown/empty board is a 200 with the empty packet (the
  spec's empty-board edge case), unlike `/hq/context`'s 404.
- The turn now honors `hq.context_budget_tokens`; it used to assemble at
  the hard-coded 6000 while `/hq/context` read the setting.
