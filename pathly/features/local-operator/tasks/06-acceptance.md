# Acceptance: propose → confirm → exactly one action

Type: task
Status: claimed
Blocked by: 02, 03, 04, 05
Test first: no

Runs the spec's bar end to end.

Automated (`tests/local_operator/test_acceptance.py`, model stubbed
with a scripted tool-call reply — no real model needed):

1. "rerun the failed test stage" → loop emits a confirmation
   proposal for `retry_stage` with the settled args.
2. After simulated approval → exactly one `retry_stage` API call
   executes; the audit log gains one `local-operator` record.
3. Without approval → zero API calls, zero audit records.
4. The offered tool schema contains exactly the 6 settled tools —
   `answer_question`, `directive`, `settings` are absent
   (assert on the schema the loop hands the model).
5. The full per-ticket Test command from commands.md passes.

Manual (record in the Answer): Studio dev, Operator mode with
Qwen3-8B, "pause the builder" on a live run → card → Run → run
pauses; note any model misbehavior (wrong tool, wrong args) in one
line.

## Not in this ticket

- Quality-grading the local model across phrasings: follow-up work;
  the manual note here is the baseline.

## Done when

- `python -m pytest tests/local_operator/test_acceptance.py -q -p no:cacheprovider` passes and prints passed.
- The `## Answer` records the manual Qwen3-8B check.

```check
$ python -m pytest tests/local_operator/test_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Goal and the bar, § Happy path
- commands.md (full Test command)

## Answer

### Progress 2026-10-14 (claimed — the in-app Run check is still to do)

Automated: `tests/local_operator/test_operator_acceptance.py` (3 tests,
green). **Renamed** from the ticket's `test_acceptance.py`: that basename is
taken by `tests/hq_copilot/test_acceptance.py`, and pytest without
`__init__.py` fails collection on duplicate basenames (repo rule). The bar
runs as `python -m pytest tests/local_operator/test_operator_acceptance.py
-q -p no:cacheprovider`. Covers 1–4: "rerun the failed test stage" → a
`retry_run` card with the run id from the packet; after Run exactly one
retry call + one `local-operator` audit record; without the click zero
calls and zero records; the offered tools are exactly the enabled ∩
available set, forbidden names absent. 5: the per-ticket Test command's
domains pass inside the full suite (2466 passed, 14 skipped; the 3 known
environmental code_intel LSP tests deselected).

Real model, headless (Qwen3 8B Q4_K_M, node-llama-cpp 3.22.1, Fast,
16k context, the real operator turn for board `04-unified-gateway` built
from a read-only DB connection, record-only handlers as in `llm:chat`):

| Message | Proposals | Time |
|---|---|---|
| what needs my attention? | none — answered from the packet | 4.5 s |
| post a note saying the review starts at 3pm | `post_note("The review starts at 3pm.")` | 3.3 s |
| stop run e21ab2a3 | `stop_run("e21ab2a3")` | 3.3 s |
| rerun the failed test stage | `retry_run("b93531bd-…")` — the board's errored team-build run, full id | 3.7 s |
| answer the builder's question with yes | refused before the model | — |

No wrong tool or wrong args. One fix from it: the handler's reply was
third-person and the model echoed "the user will see a card"; reworded
(`PROPOSED_REPLY`) and the answers now read "…waiting on the card below for
your Run click."

Still to do: the manual in-app check (Studio restarted on this code —
main-process and server changes need it): Actions on, "pause the builder"
on a live run → card → Run → the run pauses; Cancel does nothing.

### In-app check 2026-10-14 (Studio restarted on this code, Qwen3 8B built-in, Deep)

Driven over CDP on board `board-differ`:

- Composer: Actions chip `0/8` → presets "Run control" + "Board note" →
  `5 of 8 enabled`, meter adds the actions' cost (347 tokens); ticks
  persist across a Studio restart.
- "post a note saying the HQ operator test passed" → card "Post a note to
  board-differ: …" (changes state, Run / Cancel), context line "· 5 actions"
  → **Run** → card "✓ done"; the board shows the human note and the
  `local-operator` status audit line (DB: `author_source=system`), live.
- A second note → **Cancel** → "– cancelled · nothing ran", zero rows.
- "stop run e21ab2a3" (stale in run_history, not live) → the model proposed
  `stop_run`; the server check made it "✗ not proposed · no run … on this
  machine" — no Run button.
- "answer the builder question with yes" → refused before the model.
- Settings → Intelligence → HQ actions renders the catalog with risk words.

Found and fixed in-app: Deep answers ended in a literal `</think>` (Qwen3
emits its end-of-thought token as plain text after a function call; not
reproducible headlessly) — main strips think tags from answer text
(`main/ipc/llmText.ts`). Not done: pausing a LIVE run (none running; starting
one spends cloud money) — the pause path is covered by the mapping tests
against a registry run. One unexplained reset of the composer ticks to 0
during the session did not reproduce (step-by-step: open, presets, Escape,
send all keep them); likely an interaction in the app at the same time.
