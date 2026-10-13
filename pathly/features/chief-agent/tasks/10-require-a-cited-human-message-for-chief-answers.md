# Require a cited human message when the chief answers an agent

Type: task
Status: open
Blocked by: 08, 09
Test first: yes

A pending agent question must only be answered by the chief with something the human typed in the
same chief session after the question was asked. That timing is the user's decision for
cited answers; if the user later switches to "any human message of the session", drop the
`asked_at` and `ts` comparisons below and keep the rest (spec.md § Decisions, "Where the
cited-answer rule lives"; map.md § Open questions).

Keep the question on the run's state. In `supervisor/state.py` add
`_agent_question: Optional[dict] = field(default=None, repr=False, compare=False)` next to
`_awaiting_agent_answer`. In `supervisor/interactions.py::_await_agent_question`, set it under
`_lock` together with `_awaiting_agent_answer = True` to
`{"question": question_text, "options": options, "asked_at": time.time()}`, and set it back to
`None` on every exit (answered and aborted). Nothing else in the loop changes.

Add the cite rule to the chief gate for the `answer` action, in its own module (for example
`http_server/chief_cite.py`) called from `chief_gate`. A chief-token request is refused with 403
`{"error": "cite a human message from this chief session"}` unless the body's `cite` names a
`chief_human_messages` row that:

- has `kind == "human"` (the style prompt cannot be cited) and the session's `run_id`;
- for `/runner/agent-answer`: was recorded at or after the topic's `_agent_question["asked_at"]`,
  and the topic's `RunnerState.project_root` belongs to the session's project (look the state up
  with `supervisor.get_state(topic)`; a topic that is not awaiting an answer is left to the route,
  which already answers it);
- for `/comms/answer`: was recorded at or after the `ts` of the `question_id` message.

On success the gate calls `queries.chief.record_citation(run_id, cite, route, topic or
question_id)` and lets the route run. Callers without a chief token are unchanged. A codex chief
has no recorded human messages, so every answer it relays is refused; the 403 says so when the
session's engine is not `claude`.

Living docs: the cited-answer rule in the "Chief gate" paragraph of
`src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- Listing pending questions for the chief (`GET /chief/inbox`): round two, which reads the
  `_agent_question` field added here.
- Answer rules for non-chief callers: unchanged.

## Done when

- `python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` passes and
  covers, with a `RunnerState` registered under a topic and `_await_agent_question` running in a
  thread: while waiting, the state holds the question text and `asked_at`; an operator chief's
  `/runner/agent-answer` without `cite` is 403 and the thread is still waiting; citing the style
  prompt, a message from another session, or a human message recorded before the question is 403;
  citing a human message recorded after it is 200, the thread returns that answer,
  `_agent_question` is back to None and one `chief_citations` row exists; the same rules hold for
  `/comms/answer` against a board `question` row; a request with no token answers as before.
- `python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider` still passes (about a
  minute).

```check
$ python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("Where the cited-answer rule lives"), § Edge cases
- `src/pathly_orchestrator/supervisor/interactions.py`, `supervisor/api.py::supply_agent_answer`
- `src/pathly_orchestrator/http_server/blueprints/runner/api_control.py::runner_agent_answer`
  and `blueprints/comms/messages_crud.py::comms_answer` (read-only: the rule lives in the gate)
- Do not patch the global `time.sleep` in these tests; `_await_agent_question` polls with it and
  the WAL checkpoint daemon shares it

## Answer
