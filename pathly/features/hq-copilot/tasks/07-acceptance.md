# Acceptance: HQ answers from real board facts and changes nothing

Type: task
Status: resolved
Blocked by: 02, 03, 04, 05, 06
Test first: no

Runs the spec's bar end to end. Fixture board: 2 goals (one with 3/5
tasks done), 1 running run at a known stage, 1 unanswered agent question.

Automated (`tests/hq_copilot/test_acceptance.py`, model stubbed with a
recording stub that echoes the packet's question titles and run stage —
no real model needed):

1. `build_hq_prompt("what needs my attention?", board)` output names
   the pending question and the running run's stage (assert on the
   packet-derived facts the stub echoes).
2. Snapshot the DB (comms messages, run rows, fsm events) before and
   after the full HQ answer path; the diff is empty — nothing started,
   stopped, posted, or answered.
3. "restart the builder" returns the read-only redirect with zero
   model invocations.
4. The full per-ticket Test command from commands.md passes.

Manual (record the outcome in the Answer): open Studio dev, select the
fixture board, ask HQ "what's happening?" with Phi-4 Mini downloaded:
the answer references real board facts and the context manifest expands.

## Not in this ticket

- Load or latency benchmarking: follow-up work, not the bar.
- Hallucination grading beyond the fixture: the stub proves grounding
  plumbing; model quality is tracked against the recommended-models
  note in the reply below.

## Done when

- `python -m pytest tests/hq_copilot/test_acceptance.py -q -p no:cacheprovider` passes and prints passed.
- The `## Answer` records the manual Studio check (model used, what the
  answer got right, any hallucination observed).

```check
$ python -m pytest tests/hq_copilot/test_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Goal and the bar, § Stories
- commands.md (full Test command)

## Answer

Automated acceptance implemented 2026-10-14 in
`tests/hq_copilot/test_acceptance.py` (3 tests, green):

1. Fixture board (2 goals, one 3/5 tasks done; 1 running `single` run
   with an `agent_invocations` stage row `BUILDING`; 1 unanswered
   agent question): `build_hq_prompt("what needs my attention?",
   board, project_root)` output names the pending question, the
   run's `BUILDING` stage, and `3/5 tasks done` (asserted on the
   packet lines a recording model-stub echoes — the grounding
   plumbing, no real model).
2. DB snapshot (`comms_messages`, `run_history`, `fsm_events`,
   `agent_invocations`, `run_log`) before/after the full HQ answer
   path (`prepare_hq_prompt` + `build_hq_prompt` +
   `GET /hq/context` + the refusal path): diff is empty.
3. `"restart the builder"` → `HQ_READONLY_REDIRECT` with zero
   `build_hq_prompt` invocations (counting stub).

Supporting change: `build_hq_prompt` / `prepare_hq_prompt` gained an
optional `project_root` (backward compatible) so the live-runs
section isn't silently cut in the acceptance fixture.

Full per-ticket Test command
(`pytest tests/comms_board tests/db tests/http_api tests/hq_copilot
-q -x -p no:cacheprovider`): 921 passed, 2 skipped, 2026-10-14
(clean clone at the Mac's commit era, venv on the assistant's
machine). Along the way the suite caught a real regression: the
`project_root` signature extension broke the ticket-04 counting
stub — fixed in `test_guardrails.py`, suite re-run green.

Manual Studio check (needs the Mac): STILL PENDING — open Studio
dev, select the fixture board, ask HQ "what's happening?" with
Phi-4 Mini downloaded; record model used, what the answer got
right, any hallucination observed.

Manual Studio check (needs the Mac): PENDING — open Studio dev,
select the fixture board, ask HQ "what's happening?" with Phi-4
Mini downloaded; record model used, what the answer got right, any
hallucination observed.

### Review follow-up 2026-10-14

- The fixture's question used `options=["yes","no"]`; agents post option
  OBJECTS. On the real DB the `local-usage-meter` board raised
  `expected str instance, dict found` and lost its whole packet. Fixture
  now posts `{id,label,description}` objects under a goal, and asserts the
  labels and goal title render.
- The acceptance path now drives `POST /hq/prompt` (what Studio calls), and
  the no-writes check diffs every ROW of comms_messages, run_history,
  fsm_events, agent_invocations, run_log and app_settings (row counts could
  not see an UPDATE).
- Verified against a copy of the real DB: both boards with pending
  questions assemble (1.0k / 1.5k tokens of 6k, all five sections).
- Per-ticket Test command: 941 passed, 2 skipped. Manual Studio check:
  still pending — no local model is downloaded on this Mac.

### Real-model check 2026-10-14 (headless; the UI pass is still the user's)

Model: **Qwen3 8B** Q4_K_M via node-llama-cpp 3.22 / Metal on the user's
24 GB Mac, fed the exact `POST /hq/prompt` turn (copy of the real DB) with
Studio's generation settings. "what needs my attention?":

- `local-usage-meter`: named the pending statusline question with both
  real options, goal progress 0/2 and 1/2, real artifacts. 16 s.
- `lum-budget-layer` (7 pending questions): led with [PRE-C] (the P0
  go/no-go gate) and [OPEN-F], contingent tasks, research questions —
  every cited id/line is in the packet. 23 s.
- Hallucination: none of fact. Reasoning slips: once filed a 5/5 goal
  under "Incomplete Goals"; small-model quality, not grounding.
- Found + fixed on the way: answers truncated at maxTokens 1024 (Qwen3's
  silent reasoning counts against it — 552 + 469); now 2048 with a
  768 thought budget. Context capped at exactly 16k (was growing to 41k).
  Download path bugs: Phi-4 Mini URI 401'd; downloads saved as
  `hf_unsloth_*.gguf` and could never load. Default model → Qwen3 8B.

### In-app check 2026-10-14 — resolved

The manual check is the one recorded in ticket 06's "In-app check": real
boards answered by Qwen3 8B in the running app (Deep reasoning, board name,
Markdown, section choice), Fast at 2.4 s headlessly. `tests/hq_copilot` 58
passed (one new: per-section token sizes).
