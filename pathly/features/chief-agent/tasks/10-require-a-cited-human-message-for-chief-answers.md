# Require a cited human message when the chief answers an agent

Type: task
Status: open
Blocked by: 08, 09
Test first: yes

A pending agent question must only be answered by the chief with something the human typed in the
same chief session after the question was asked, and each typed message can answer one question.
The chief does not write the answer: it names the message with `cite`, and Pathly relays that
message's own text. That timing is the user's decision for cited answers; if the user later
switches to "any human message of the session", drop the `asked_at` and `ts` comparisons below and
keep the rest (spec.md § Decisions, "Where the cited-answer rule lives" and "What a citation
proves"; map.md § Open questions).

Keep the question on the run's state. In `supervisor/state.py` add
`_agent_question: Optional[dict] = field(default=None, repr=False, compare=False)` next to
`_awaiting_agent_answer`. In `supervisor/interactions.py::_await_agent_question`, set it under
`_lock` together with `_awaiting_agent_answer = True` to `{"question": question_text, "options":
options, "questions": questions, "asked_at": time.time()}`, and set it back to `None` on every
exit (answered and aborted). `question` and `options` are the first question, as today;
`questions` is the whole list the agent sent. Today the function keeps only `questions[0]`, so an
AskUserQuestion with several questions loses the rest; with the full list on the state, round
two's inbox can show every question, and the user's one cited message answers them together (the
agent receives one answer string, as it does now). The `AGENT_QUESTION` broadcast and the rest of
the loop do not change.

Add the cite rule to the chief gate for the `answer` action, in its own module (for example
`http_server/chief_cite.py`) called from `chief_gate`. A chief-token request is refused with 403
`{"error": "cite a human message from this chief session"}` unless the body's `cite` names a
`chief_human_messages` row that:

- has `kind == "human"` and the session's `run_id` (the style prompt and a `relayed` message from
  another session cannot be cited);
- for `/runner/agent-answer`: was recorded at or after the topic's `_agent_question["asked_at"]`,
  and the topic's `RunnerState.project_root` belongs to the session's project (look the state up
  with `supervisor.get_state(topic)`; a topic that is not awaiting an answer is left to the route,
  which already answers it);
- for `/comms/answer`: was recorded at or after the `ts` of the `question_id` message.

The chief sends the citation, never the words:

- A chief-token body that carries `answer` or `option_id` is 403 `{"error": "send cite only:
  Pathly relays the cited message's text"}`. The chief cannot word the answer, and it cannot pick
  an option on the user's behalf. Any explanation of its own goes on the board as a separate
  `note`.
- On success the gate sets `flask.g.chief_cited_text` to the cited message's `text`. Add
  `chief_cite.answer_text(data) -> str`: `g.chief_cited_text` when set, else
  `data.get("answer", "")`. `api_control.py::runner_agent_answer` and
  `messages_crud.py::comms_answer` read the answer through it instead of `data.get("answer", "")`
  (one line each plus a lazy import; `messages_crud.py` is at 395 lines, so it stays under 400).
  Callers without a chief token get exactly what they sent, as today.
- Why the server relays and the chief does not retype: the chief calls the API through `pathly
  api` with a shell-quoted JSON argument, and retyping the user's words there breaks on
  apostrophes, quotes and line breaks. A word-for-word comparison would refuse honest answers, and
  a chief that never supplies the text cannot change it.
- A message can be cited once. `record_citation` returns False for a second use, and the gate
  answers 403 `{"error": "that message was already cited"}`. To answer two questions, the user
  types twice.

Human escalations (#63): `/comms/acknowledge` on an escalation with `to_agent = "human"` is an
`answer` call (ticket 08). It needs a `cite` naming a human message of the session recorded at or
after the escalation's `ts`; it carries no text, so `answer_text` is not involved. On success the
gate records the citation and sets `flask.g.chief_cited_gate = message_id`, and
`blueprints/comms/_helpers.refuse_agent_on_human_gate` lets a live chief token through only when
that flag names the same id. Every other run token is refused as today. `/comms/delete` on a human
escalation stays refused for the chief (ticket 08 does not list it), and the FSM's
`force_past_gate` stays a human-only affordance.

On success the gate calls `queries.chief.record_citation(run_id, cite, route, topic or
question_id or message_id)` and lets the route run. Callers without a chief token are unchanged. A
codex chief has no recorded human messages, so every answer it relays is refused; the 403 says so
when the session's engine is not `claude`.

Living docs: the cited-answer rule in the "Chief gate" paragraph of
`src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- Listing pending questions for the chief (`GET /chief/inbox`): round two, which reads the
  `_agent_question` field added here, `questions` included.
- Showing every question of a multi-question ask in HQ's `AgentQuestionCard`: HQ keeps showing
  the first one. HQ stays beside the Chief (map.md § Open questions, "Chief and HQ"), so the card
  stays where it is.
- Answer rules for non-chief callers: unchanged.
- Proving the user meant the cited message as the answer to this particular question: the rule
  binds the user's real words to the question the chief picked, not the user's intent. A chief
  that cites an unrelated later message relays the user's real words to the wrong question; only
  the user reading the board catches it. The acceptance test documents this limit.

## Done when

- `python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` passes and
  covers, with a `RunnerState` registered under a topic and `_await_agent_question` running in a
  thread: while waiting, the state holds the question text, `asked_at`, and every question of a
  two-question ask in `questions`; an operator chief's `/runner/agent-answer` without `cite` is
  403 and the thread is still waiting; citing the style prompt, a `relayed` message, a message
  from another session, or a human message recorded before the question is 403; a body with
  `cite` and an `answer` of the chief's own is 403; citing a human message recorded after the
  question, with no `answer`, is 200, the thread returns that message's text exactly,
  `_agent_question` is back to None and one `chief_citations` row exists; citing the same message
  again for a second question is 403; the same rules hold for `/comms/answer` against a board
  `question` row (the stored answer is the cited text), and `option_id` from the chief is 403; an
  operator chief acknowledges a `to_agent: "human"` escalation with a cite recorded after it (200,
  the gate's flag lets it past `refuse_agent_on_human_gate`), and gets 403 without a cite and
  with a cite recorded before it; a builder token acknowledging the same escalation is still 403;
  a request with no token, and a builder token's answer, are answered with the `answer` they sent.
- `python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider` still passes (about a
  minute).
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- spec.md § Decisions ("Where the cited-answer rule lives", "What a citation proves"), § Edge
  cases
- `src/pathly_orchestrator/supervisor/interactions.py` (keeps only `questions[0]` today),
  `supervisor/api.py::supply_agent_answer`
- `src/pathly_orchestrator/http_server/blueprints/runner/api_control.py::runner_agent_answer`
  and `blueprints/comms/messages_crud.py::comms_answer` (each reads `data.get("answer", "")`;
  that one read moves to `chief_cite.answer_text`), `comms_acknowledge` (read-only)
- `src/pathly_orchestrator/http_server/blueprints/comms/_helpers.py::refuse_agent_on_human_gate`
  and `src/pathly_orchestrator/fsm_human_gate.py` (#63)
- Do not patch the global `time.sleep` in these tests; `_await_agent_question` polls with it and
  the WAL checkpoint daemon shares it

## Answer
