# Require a cited human message when the chief answers an agent

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/supervisor/state.py`: `_agent_question: Optional[dict]` next to
  `_awaiting_agent_answer`. `supervisor/interactions.py::_await_agent_question` sets it under
  `_lock` with `_awaiting_agent_answer = True` to `{question, options, questions, asked_at}`
  (`questions` is the whole list of the ask; `asked_at` is `time.time()`), and sets it back to
  None on both exits (answered, aborted). The `AGENT_QUESTION` broadcast and the loop are as before.
- `src/pathly_orchestrator/http_server/chief_cite.py` (new, 153 lines): `cite_refusal(rule, session,
  conn, bodies)` and `answer_text(data)`. `chief_gate.py` (172 lines) calls it through
  `_cite_refusal` after every reading of the body has passed every other check, once, so the
  citation is spent only for a call the gate lets through.
- `blueprints/runner/api_control.py` (`runner_agent_answer`) and `blueprints/comms/messages_crud.py`
  (`comms_answer`, 396 lines) read the answer through `answer_text` (one line plus a lazy import
  each). `blueprints/comms/_helpers.py::refuse_agent_on_human_gate` lets a run token through when
  `g.chief_cited_gate` names the escalation it was asked about.
- No change to `chief_routes.py` or `chief_field*.py`: `cite` was already a listed key (kind `id`) on
  the three routes (ticket 08), and `answer` / `option_id` stay listed on `/comms/answer`
  (`option_id` is not a key of `/runner/agent-answer`, see Decisions).
- Tests: `tests/http_api/test_chief_cited_answers.py` (26 tests, the Done-when cases),
  `test_chief_cited_edges.py` (35), `chief_cite_support.py` (`Session`, `Asker`, helpers). Edits to
  existing test files, each because the new rule legitimately changes what a chief may send, none
  to an assertion's strength: `chief_walk_support.py` (`BODY_HELPER_MODULES`: the key tests follow
  `chief_cite.answer_text`, else `answer` looks read by no view and
  `test_a_listed_key_is_read_or_is_a_url_variable_or_waits_for_a_ticket` fails),
  `chief_audit_calls.py` / `chief_audit_world.py` (the audit's answer baselines cite a fresh message
  per request instead of sending `answer`; `register_asking_run` sets `_agent_question`; a new
  `ack a human escalation` variant), `test_chief_gate_bodies.py` (the two `/runner/agent-answer`
  body tests cite instead of sending `answer`; the other-project one now also asserts the project
  error, so it no longer passes because of "send cite only"), `test_chief_gate.py` (one test: an
  operator's acknowledgement of a human escalation without a cite is now the gate's 403, not the
  human gate's). `tests/INDEX.md` and `tests/http_api/INDEX.md` regenerated.
- Living docs: `src/pathly_orchestrator/CLAUDE.md` ("Chief gate": the `answer` row, a "Cited answers"
  bullet with what a citation proves and does not, the `cite` sentence of "One project", the
  `/clear` line of "Human messages", the package map for `chief_cite.py` and `interactions.py`, the
  `/runner/agent-answer` line); `map.md` (one Decisions line) and `learnings.md` (three lines).

**Proof** (each run fresh, after the last edit to code or tests; the ticket, map and learnings were
edited afterwards)

- Test first: commit `cac9792` `test(chief-agent): 10 failing test` holds only test files. At that
  commit `python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` ->
  `23 failed, 3 passed`, exit 1 (the 3 are the cases that must stay as they are: callers without a
  chief token, a builder token on a human escalation). The failures were the right ones:
  `AttributeError: 'RunnerState' object has no attribute '_agent_question'`, the route's own `400
  Field 'answer' must be a non-empty string` where the gate should have answered 403 (a chief's
  `cite` with no `answer` reached the route), and `ModuleNotFoundError ... chief_cite`.
- `python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` -> `26 passed
  in 7.86s`, exit 0. It covers, with a registered `RunnerState` and `_await_agent_question` in a
  thread: the state holds the question text, `asked_at` (between the test's own clock reads), the
  options and both questions of a two-question ask, and the `AGENT_QUESTION` broadcast is unchanged;
  `_agent_question` is None after an answer and after an abort; an operator's `/runner/agent-answer`
  without `cite` is the gate's 403 `cite a human message from this chief session` and the thread is
  still waiting; the style prompt, a `relayed` message, another session's human message and a
  human message recorded before the question are each that 403 (waiting, no `chief_citations` row);
  `cite` with an `answer` of the chief's own is 403 `send cite only: Pathly relays the cited
  message's text`; a message recorded after the question gives 200 `{status: accepted, topic}`, the
  thread returns the text exactly (`use CSV, it's what "ops" asked for\nand keep the header row`),
  `_agent_question` is None and one `chief_citations` row has the route and topic; the same message
  for a second question is 403 `that message was already cited` (second question still waiting),
  and a message older than a later question is 403; the same rules for `/comms/answer` against a
  `question` row (the stored `answer` message is the cited text; `option_id` and `answer` from the
  chief are 403); an operator acknowledges a `to_agent: "human"` escalation with a cite recorded after
  it (200, the flag lets it past `refuse_agent_on_human_gate`, one citation row for
  `/comms/acknowledge`), gets 403 without a cite and with a cite recorded before it (not
  acknowledged), and a builder token still gets the human gate's 403; no token and a builder
  token get the `answer` they sent on both routes, no citation and no human message stored.
- `python -m pytest tests/http_api/test_chief_cited_edges.py -q -p no:cacheprovider` -> `35 passed in
  10.94s`: `cite` as a string, float, list, object, null, negative, unknown id or `True` (with a
  `human` row numbered 1) is refused; a message stamped exactly `asked_at` (or exactly the question
  row's `ts`) counts and one 1 ms earlier does not; a `ts` that cannot be read is refused; UTF-8 BOM,
  UTF-16 and UTF-32 bodies are cited like plain ones and hide no `answer` on either route; a topic
  of another project is 403 `that is not this chief's project`; a topic with no run is the route's
  404, a run that is not awaiting the route's 409; a topic that is blank, null or a number is the
  route's 400 and spends nothing; a codex session's refusal names codex; a chief can still cite an
  unrelated later remark (the documented limit); `answer_text`, the flag of
  `refuse_agent_on_human_gate` (one id only), disagreeing readings and "every answer route has a
  target key" are pinned.
- `python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider` -> `317 passed in 67.81s`, exit 0.
- `python scripts/check_file_size.py` -> `OK: 1028 source files checked; 18 known over 400 lines, none
  new, none grown.`, exit 0.
- Beyond the Done-when: `python -m pytest tests/ -q -p no:cacheprovider` (the whole suite, for the
  basename rule) -> `5048 passed, 14 skipped in 1115.32s`, exit 0 (the skips are older tests, none in
  my files). Python 3.13 venv: the two new files, `test_chief_gate.py`, `_bodies`, `_keys`,
  `_strict_keys`, `_tables`, `_kinds` -> `383 passed`; `test_chief_gate_audit.py` and
  `test_chief_gate_separators.py` -> `130 passed in 281.75s`. Python 3.12: all of `tests/http_api`
  (including the audit and the URL-variable tests) `exit 0` before the last two tests were added to
  the edges file, and inside the full run after. `datetime.fromisoformat` on `+00:00`, `Z`, no
  offset and garbage gives the same on 3.11, 3.12 and 3.13 (`python3.NN -I`).
- Lint chain from `commands.md`, link by link: `black --check src/ tests/` (637 unchanged), `mypy`
  (`no issues found in 333 source files`), `check_file_size.py`, `check_no_mirror_reads.py`,
  `gen_test_index.py --check`, `lint-imports` (`1 kept, 0 broken`), `bandit -q -r src/ -ll -x
  src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`, the Smoke import, and `python -m
  build --wheel` (the wheel holds `chief_cite.py`): all exit 0. No `# noqa`, `# nosec`, `type:
  ignore` or skip added.
- Mutation check (`scratchpad/mutate10.py`, one-line breakages run against the two new files, each
  restored): 22 of 22 caught after adding one test. Kind check off, session check off, `bool`/string
  accepted as `cite`, `<=` for `<`, timing off, project check off, citation not spent,
  `answer`/`option_id` allowed, `answer_text` ignoring the flag, a bad `ts` accepted, flag never
  set, flag for any id, flag always, gate skipping the rule, gate not seeing an acknowledgement as
  an answer, question not cleared on answer / on abort, only the first question kept, `asked_at`
  0, either route ignoring the cited text. One survived the first run (readings of the body that
  disagree), because no body makes the gate's two readings differ; `test_readings_of_the_body_that_
  disagree_are_refused` calls the rule with two readings and catches it.

**Decisions**

- Refusals use the gate's usual body `{error, action, tier, allowed}` (action `answer`), a superset
  of the ticket's `{"error": ...}`, so a test tells the gate from the route with `allowed` as for
  every other refusal.
- The order inside the gate: the key allowlist (`key_refusal`) runs inside `_refusal` as before, so
  an unlisted key is still named first; the cite rule runs after all of it. `answer` is a listed
  key of both routes, so it gets "send cite only"; `option_id` is listed only on `/comms/answer`, so
  on `/runner/agent-answer` it gets the allowlist's "'option_id' is not a key a chief may send to
  this route" (still a 403; the route reads no such key). Moving the cite-only check ahead of the
  allowlist would have changed what `test_chief_gate_strict_keys.py` asserts.
- `cite` must be a JSON integer (`type(cite) is int`): `True`, `1.0` and `"1"` are refused, so a
  chief cannot hit message 1 with a boolean or a number-looking string.
- Readings of the body must agree on `cite` and on the target (`topic`, `question_id`,
  `message_id`), because a route reads one of them and the gate cannot know which; any `answer` or
  `option_id` in any reading is refused.
- A target the route would reject for its own shape (a blank or non-string `topic`, `question_id`)
  is left to the route with no cite effect: the route checks the target before the answer, answers
  400, and nothing is spent or relayed.
- A topic with no run, a run that is not awaiting, and a `question_id` with no row take the
  project check (when a run exists) but not the time check, as the ticket says, and the citation
  is spent: the route then answers 404/409/404. I chose spending over "set the text and do not
  record", because a run could start asking between the gate and the route and the unrecorded
  message could then be relayed to a question it predates and cited again.
- The human-escalation flag is `g.chief_cited_gate = <the message_id the body named>` and the
  helper compares it with the id it is asked about; `g.chief_cited_text` is not set for an
  acknowledgement (it carries no words).
- `/runner/agent-answer` still strips the answer before it supplies it (for everyone), so outer
  whitespace of a cited message does not reach the agent; `/comms/answer` only checks that the
  stripped text is not blank and stores the cited text unstripped.
- `chief_walk_support.BODY_HELPER_MODULES` names one module outside `blueprints/` for the key tests
  to follow. The alternative, adding `answer` to `WAITS_FOR_A_TICKET`, would have said "no view
  reads it" for a key the routes do read.
- Audit: the answer baselines cite `w.fresh_cite` (a new message per request, because each cite is
  spent), so the audit still reaches the answer sinks (`REACHES` covers them) and
  `/comms/acknowledge` now has a human-escalation variant that reaches the new flag.

**Shortcuts taken**

- The citation is spent at the gate, before the route runs, as the ticket says. A route that then
  answers 404, 409 or 500 has used the person's message; they type again. It stops being right if
  chiefs often name topics that are not pending; the upgrade is to release the citation when the
  response is not 2xx (an `after_request` that deletes the row), which needs a delete query and
  loses the "unique forever" property in the failure window.
- The gate checks the question when the request arrives and the route relays a moment later. If the
  run's question changes in that window the cited message goes to the new question although it
  may predate it. The words are still the person's. Closing it needs the check and the relay under
  one lock (a `supply_agent_answer(topic, answer, not_before=...)`), which is a change to
  `supervisor/api.py` this ticket does not call for.
- `/comms/answer` is bound to a project only by ticket 14 (`question_id` is an unbound id): a chief
  can cite for a question of another project's board here. The same holds for the escalation id of an
  acknowledgement.
- `/comms/answer` on a human-escalation id spends the citation and then meets the human gate's 403
  (only `/comms/acknowledge` sets the flag).
- Not measured: a pasted prompt arrives wrapped in `<pasted_content ...>` lines in some claude
  sessions (ticket 09 left it open); such a message would be relayed with those lines.
- What a `human` row proves, said once here as the ticket asks: it is a prompt claude delivered to the
  chief's tab with none of the wrappers ticket 09 measured, not proof that a person typed it. Against
  an `operator` chief, which can start a headless agent, that agent runs as the same OS user and
  can read the session's secret file and `--session-id` and post a `human` row to
  `POST /chief/human-messages` itself. The cite rule makes a chief unable to word an answer or pick
  an option; it does not make the answer the person's against such an agent. `/clear` in the tab
  changes claude's session id, so afterwards the hook records nothing and the chief has nothing
  citable until the tab is reopened (the living doc says both).

**For later tickets**

- Ticket 13 (acceptance): an answer scenario must give the chief a `cite`, not an `answer`; the
  helpers `Session`, `Asker` and `post_row` in `tests/http_api/chief_cite_support.py` do it.
  `RunnerState._agent_question` holds `questions` for round two's `GET /chief/inbox`.
- Ticket 14 (bind id-addressed calls to the chief's project): `/comms/answer`'s `question_id` and
  `/comms/acknowledge`'s `message_id` are the ids to bind; the cite rule reads their rows (`ts`) and
  does not check their board or scope.
- Ticket 17 (`chief-connect`, `pathly api`): the chief's text should say that an answer is
  `{"topic"|"question_id": ..., "cite": <number from the hook's line>}` and nothing else, that a
  message answers one question and must be typed after it, that a refusal "cite a human message ..."
  means to ask the person to type the answer in the tab, and that `/clear` ends recording.
- Ticket 15 (`max_cost_usd`) deletes its `WAITS_FOR_A_TICKET` line as planned; the `cite` lines stay,
  because the gate reads `cite` and no view does. The comment above `WAITS_FOR_A_TICKET` in
  `test_chief_gate_keys.py` ("Ticket 10 reads `cite` ...") is now only half true (the gate reads it);
  I did not touch that file.

**Minors noticed, not fixed**

- `test_chief_gate.py::test_an_operator_acknowledges_an_ordinary_row_and_meets_the_human_gate` keeps
  its name, but its second half now asserts the gate's cite refusal rather than "meets the human
  gate" (the human gate is covered in `test_chief_cited_answers.py`); renaming it would look like a
  deleted test to the floor scan.
- `chief_field_calls.py` still says of `_CITE` "(ticket 10 reads it)"; true of the gate, not of a view.
- The hook still prints "cite it with cite=<id> when you relay an answer." for every `human` message,
  including one typed before any question; harmless, the chief cites what the question needs.

**Review fixes (round 1)** (quality review of `b1af9ee`; the round starts at `030c05b`. Test-only
commit first: `1409409`, which holds only test files. Run on the unchanged `src/` it gave
`python -m pytest tests/http_api/test_chief_cited_edges.py tests/http_api/test_chief_cited_escalations.py
tests/http_api/test_chief_gate_keys.py tests/http_api/test_chief_gate.py
tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` -> `10 failed, 260 passed`. The 10
are the right ones: the two new int64 cases of `test_cite_is_a_message_number_and_nothing_else`
(`OverflowError: Python int too large to convert to SQLite INTEGER`) and the 8 cases of
`test_a_chief_cannot_close_a_human_escalation_as_anyone_else` (agent `human`, `Human`, `Chief`,
`chief ` got the route's 200; `""`, `7`, `null` and an absent agent got the route's 400, where the gate
should answer 403). The rest pass on the old code and are proved by mutation, below.)

1. *major, `test_true_is_not_message_number_one` could not fail for its rule.* Reproduced (the round-0
   file passes 61 of 61 under `not isinstance(cite, int)`) and fixed. The converted row (message 1, the
   style prompt) is now `kind = 'human'` with `ts = asked_at + 1`, set after the question is asked, so it
   is citable on every count but the type of `cite`. The test also cites the same row by its number
   afterwards and sees 200 and the style prompt's text: a positive control, so a refusal can only be
   about the type. Mutation proof (below): under `not isinstance(cite, int)` the new test fails.
2. *minor, a `cite` outside int64 was a 500.* Fixed in `chief_cite._cited_message`: `type(cite) is not int
   or abs(cite) >= 2**63` is "no such message", the same 403 as any bad cite, before any query. The
   cite-shape test has two new cases (`2**63`, `-(2**63) - 1`). (`-2**63` is a valid int64 and is
   refused too: negative, so never a row id.)
3. *minor, the `.strip()` sentence.* Fixed in `src/pathly_orchestrator/CLAUDE.md` ("Cited answers") and
   in the `chief_cite` docstring, which had no `.strip()` sentence but its "the words ... are the
   person's" line implied none: `/runner/agent-answer` strips the answer before it supplies it (so
   outer whitespace of a cited message does not reach the agent), `/comms/answer` strips only to see
   whether it is blank and stores the cited text unstripped.
4. *minor, "what reached the tab".* Fixed in the "What a citation proves" paragraph and the docstring:
   a `human` row is "what the hook endpoint recorded" (a forged one never reached the tab), and the
   rule guards the chief token's own calls, not a process the chief starts: a headless agent the
   operator chief starts can call `/runner/agent-answer` and `/comms/answer`, unchanged for every
   caller without a chief token, with no `cite` at all.
5. *minor, no test that `refuse_agent_on_human_gate` still holds against a cited `/comms/answer`.*
   Added `test_the_answer_route_does_not_close_a_human_escalation_for_a_chief` (a chief with a good cite
   on a `to_agent: "human"` escalation: the chief gate lets it through, the route answers the human
   gate's 403, no answer row, not acknowledged). Mutation proof (below).
6. *minor, spent citations documented too narrowly.* Reproduced each claim first with a throwaway
   request test (deleted): a `text/plain` body spends the message (route 500, from the 415 inside), a
   run that is not awaiting spends it (409), a topic with no run spends it (404), `/comms/answer` on a
   human escalation spends it (403), and a blank topic spends nothing (400). One paragraph, "What a
   spent citation costs", in `src/pathly_orchestrator/CLAUDE.md` and the same words in the
   `chief_cite` docstring: those cases, that a chief can burn any unspent message of its session by
   naming a topic with no run or an idle run and the person is not told, and that both sides of "at or
   after" are the wall clock (`time.time()` for a message and for a run's question, the row's ISO `ts`
   for a board row), so a clock stepped backwards lets an older message pass.
7. *minor, the chief chose the `agent` of the acknowledgement.* Fixed in `chief_cite.cite_refusal`:
   for `/comms/acknowledge` (the cited path, a human escalation) every reading of the body must have
   `agent == "chief"`, else 403 `a chief acknowledges a human escalation as 'chief'` (`AS_CHIEF`),
   checked before the message is looked up, so nothing is spent. A missing, null, blank or non-string
   agent is that 403 too (the route would have said 400). `test_chief_cited_escalations.py` (new file, the
   answers file has 386 lines): agent `chief` closes it and the row says `["chief"]`; `human`,
   `Human`, `Chief`, `chief `, `""`, `7`, `null` and an absent key are each the gate's 403, nothing
   acknowledged, no `chief_citations` row, and the same message then closes it with `agent: "chief"`.
   An acknowledgement of an ordinary row (the `decide` action) is not held to it.
8. *minor, stale text.* (a) `test_chief_gate_keys.py`: the name and members were wrong for `cite`.
   `WAITS_FOR_A_TICKET` now holds only `("/runs", "max_cost_usd")` and a new `READ_BY_THE_GATE` holds
   the three `cite` lines, with a comment that says why; the exemption in
   `test_a_listed_key_is_read_or_is_a_url_variable_or_waits_for_a_ticket` and the listed-or-refused check
   cover both sets, so nothing is weaker, and a new test pins `READ_BY_THE_GATE` to the rules of
   `chief_cite.TARGET_KEYS`. I kept the old test's name (ticket 08's Answer names it). (b)
   `chief_field_calls.py`: "(`chief_cite` reads it)". (c) `CLAUDE.md` board-closure table: the live
   token still gets 403 on a human escalation except a chief's acknowledgement as `chief` that cites
   a message typed after it. (d) The test in `test_chief_gate.py` is now
   `test_an_operator_acknowledges_an_ordinary_row_and_a_human_escalation_needs_a_cite`. (e) The
   `/clear` sentences (two places in `CLAUDE.md`): a message recorded before the `/clear`, for a
   question asked before it, can still be cited; nothing typed afterwards can be until the tab is
   reopened. (f) Beyond the list: the "Not here yet" paragraph still named "the cite rule for `answer`
   (10)" as a later ticket's work; removed. The package-map line of `chief_cite.py` mentions the
   `agent` rule.
9. *minor, tests that depend on the clock.* Not changed. I tried a `later()` that waits for the wall
   clock to read later than on entry instead of sleeping 20 ms, and dropped it: a board row's `ts` is an
   ISO string cut to the microsecond, so a message stamped a microsecond after a row can compare equal
   or earlier, and the "older message" tests would flake. A fix without a pause has to wait for more
   than a microsecond anyway; the 20 ms pause stays. The `Asker` thread's 50 ms poll is bounded by its 5
   s join, as before.

**Round 1 proof** (each run fresh, after the last edit to code, tests or docs; the ticket, map and
learnings were edited afterwards)

- `python -m pytest tests/http_api/test_chief_cited_answers.py -q -p no:cacheprovider` -> `26 passed in
  7.53s`, exit 0.
- `python -m pytest tests/runner_supervisor -q -x -p no:cacheprovider` -> `317 passed in 64.98s`, exit 0.
- `python scripts/check_file_size.py` -> `OK: 1028 source files checked; 18 known over 400 lines, none
  new, none grown.`, exit 0 (`chief_cite.py` is 175 lines; `messages_crud.py` is untouched at 396).
- The Test command of `commands.md` (`python -m pytest tests/comms_board tests/db tests/runner_supervisor
  tests/http_api -q -x -p no:cacheprovider`) -> `3155 passed, 2 skipped in 830.05s (0:13:50)`, exit 0 (the
  2 skips are older tests, none in my files).
- Python 3.13 venv: the five files above (`test_chief_cited_answers`, `_edges`, `_escalations`,
  `test_chief_gate_keys`, `test_chief_gate`) -> `270 passed in 50.52s`; `test_chief_gate_audit.py` and
  `test_chief_gate_separators.py` -> `130 passed in 208.61s`. Python 3.12: the same five files ->
  `270 passed in 50.47s`, and the audit and separators are inside the 3155 above.
- Lint chain from `commands.md`, link by link: `black --check src/ tests/` (638 files unchanged), `mypy`
  (`no issues found in 333 source files`), `check_file_size.py`, `check_no_mirror_reads.py`,
  `gen_test_index.py --check` (INDEX files regenerated for the new file), `lint-imports` (`1 kept, 0
  broken`), `bandit -q -r src/ -ll -x src/pathly_data/`, `check_adapters.py`, `check_entry_points.py`,
  plus `check_version_sync.py` (2.24.1): all exit 0. Smoke exit 0. `python -m build --wheel` exit 0, and
  the wheel holds `chief_cite.py` with `AS_CHIEF`. No `# noqa`, `# nosec`, `type: ignore` or skip added.
- Floor guard, after the commits: `FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3
  scripts/floor-guard.py chief-agent 10 030c05b` and the same with `a3a1da4` as the base -> `floor guard:
  clean`, exit 0 both.
- Mutation check (`scratchpad/mutate10b.py`, one-line breakages of `chief_cite.py` in a COPY of the repo
  at `scratchpad/mut10b`, imported from the copy, the repo itself untouched; each restored, `restored:
  True`), run against the four test files: `not isinstance(cite, int)` -> fails
  `test_true_is_not_message_number_one` and nothing else; no int64 bound -> both int64 cases fail;
  bound `>` instead of `>=` -> the "above int64" case fails; `g.chief_cited_gate` set for every rule
  -> `test_the_answer_route_does_not_close_a_human_escalation_for_a_chief` fails; no agent check ->
  the 8 agent cases fail; agent compared with `strip().lower()` -> the `Chief` and `chief ` cases fail;
  agent checked after the citation is spent -> the 8 agent cases fail (a citation row exists): 7 of 7
  caught. `scratchpad/mutate10b_old.py` ran the round-0 `test_chief_cited_edges.py` and
  `test_chief_cited_answers.py` (copied into the copy as `*_old.py`) under `not isinstance(cite, int)`
  and under the gate flag for every rule: `61 passed` both times, which is why neither was caught
  in round 0.

**Round 1 decisions**

- The `agent` rule is in `chief_cite`, not in the gate's `_refusal`: it applies only to the cited
  acknowledgement (the `answer` action), and it runs before the message is looked up so a refusal spends
  nothing. Equality with `"chief"` is exact, as `/comms/post`'s `from`.
- `READ_BY_THE_GATE` is a second set rather than a renamed one, so ticket 15's line and the CLAUDE.md
  text about it (`WAITS_FOR_A_TICKET` for `max_cost_usd`) stay true.
- The new tests live in `test_chief_cited_escalations.py`: `test_chief_cited_answers.py` is 386 lines.

**Round 1 shortcuts taken**

- none new. The round-0 ones stand (citation spent before the route runs; check and relay not under
  one lock; `/comms/answer` and `/comms/acknowledge` ids not bound to a project until ticket 14).

**Round 1, for later tickets**

- Ticket 17 (`pathly api` texts): an acknowledgement of a human escalation is `{"message_id": <id>,
  "agent": "chief", "cite": <number>}`, and the 403 `a chief acknowledges a human escalation as 'chief'`
  means send `agent: "chief"`. A chief should name only a topic it was told is waiting: a topic with no
  run, an idle run or a `text/plain` body spends the person's message and nobody tells them.
- Ticket 13 (acceptance): the human-escalation scenario sends `agent: "chief"` (the audit's variant
  already does); a chief cannot close it as `human`, and `/comms/answer` on an escalation stays the
  human gate's 403.

**Round 1, minors noticed, not fixed**

- An acknowledgement of an ordinary row (action `decide`) still stores whatever `agent` the chief
  sends; only the human-escalation path is held to `"chief"`.
- The `refuse_agent_on_human_gate` docstring does not mention the `agent` rule (it is the chief gate's).
- The hook still prints "cite it with cite=<id> when you relay an answer." for every `human` message.
- `later()` still pauses 20 ms (item 9).

## Review findings (round 1, quality review)

QUALITY

Range reviewed: a3a1da4..b1af9ee. The ticket's last commit is HEAD, so there are no later commits. I did not read `## Answer`. The `--stat` line for the ticket file was the only exposure.

Done-when, re-run by me:
- `test_chief_cited_answers.py`: 26 passed.
- `tests/runner_supervisor -x`: 317 passed.
- `check_file_size.py`: exit 0.

Extra runs:
- All of `tests/http_api` on 3.12: 1741 passed.
- Audit, separators, cited answers and cited edges on 3.13.16: 191 passed. The audit still gives every URL variable the whole hostile list.
- `comms_board`, `hq_copilot`, `local_operator` and `consistency`: 1097 passed.
- black, mypy, lint-imports, bandit, `check_no_mirror_reads` and `gen_test_index --check` are clean.
- The working tree is clean. My test runs left only gitignored `__pycache__` files. My probe and mutation scripts are in `/tmp/claude-0/-home-claude-pathly-adapters/5223161d-7afa-5239-b776-b281c8303b1d/scratchpad/rv10q/`.

I found no way to relay an answer or close a human escalation without a valid citation. I tried:
- Duplicate JSON keys, `answer`, BOM / UTF-16 / UTF-32 bodies, `?answer=` in the query string, a form body, and `text/plain` content type.
- `cite` as NaN, Infinity, `1e400`, bool, float, string, null, negative, unknown and a 5000-digit integer.
- `asked_at` / `ts` equality and one millisecond before.
- A question re-asked after its citation was spent.
- Six concurrent requests spending one citation: exactly one got 200.
- Another project's topic, another session's row, the style prompt and a `relayed` row.

`flask.g` is per request (Flask 3.1). Only `cite_refusal` sets the two flags, and only after `record_citation` succeeds. `_agent_question` is set and cleared with `_awaiting_agent_answer` under `_lock` on both exits. A new question overwrites the old one at its start, so I found no stale-`asked_at` leak.

1. major tests/http_api/test_chief_cited_edges.py:75-89: `test_true_is_not_message_number_one` cannot fail for the rule it names.
   - In a scratchpad copy I changed `type(cite) is not int` to `not isinstance(cite, int)` (chief_cite.py:70). All 61 cited tests still passed.
   - The test turns the style prompt (id 1) into a `human` row, but that row predates the question. So `cite=True` is refused on the timestamp (`NOT_CITED`), never on the type.
   - I confirmed a corrected test catches the mutation: with id 1 set to `kind='human'` and `ts = asked_at + 1`, `cite=True` gives 200 under the mutation and 403 on the real code.
   - Fix: make the converted row citable on every other count. Update its `ts` to `asked_at + 1` after `ask(...)`, or create the Asker before the Session. Then only the type check can refuse it.
   - Every other mutation I tried on the new rule was killed. That was 19 of 21 in the first batch, plus a project-check mutation in the second. The two survivors are this one and item 5.

2. minor chief_cite.py:72 (`_cited_message`): a `cite` outside int64, such as `9223372036854775808` or `-9223372036854775809`, raises `OverflowError` inside the `before_request` hook.
   - Result is a 500 with a traceback, not the 403 the doc promises ("Otherwise 403", CLAUDE.md:734).
   - Nothing is relayed or spent. No test covers it.
   - Fix: refuse `abs(cite) >= 2**63` in `_cited_message`, and add that case to `test_cite_is_a_message_number_and_nothing_else`.

3. minor src/pathly_orchestrator/CLAUDE.md:753 and chief_cite.py:23: "The route's own `.strip()` of the answer still applies" is true only for `/runner/agent-answer`.
   - `/comms/answer` only strips for its emptiness check and stores the text unstripped. Probe: cited `"  padded answer \n"` is stored verbatim by `/comms/answer` and relayed as `"padded answer 2"` (stripped) by `/runner/agent-answer`.
   - Fix: say which route strips.

4. minor src/pathly_orchestrator/CLAUDE.md, the "What a citation proves" paragraph (lines 760-770, quote at 766): the operator-chief caveat is honest but incomplete.
   - It says an operator chief's spawned agent can forge a `human` row, yet calls that row "what reached the tab". A forged row never reached the tab; "what the hook endpoint recorded" is accurate.
   - It does not say that a headless agent the operator chief starts needs no forgery at all. `/runner/agent-answer` and `/comms/answer` are unchanged for non-chief callers, so a builder-token or tokenless call answers with no cite. The lead sentence ("A chief answers an agent only by naming a message...") is true of the chief's own token only.
   - Fix: add one clause saying the rule guards the chief token's calls, not a process the chief starts.

5. minor tests/http_api (coverage gap): nothing tests that a chief with a valid cite is still refused by `refuse_agent_on_human_gate` when it calls `/comms/answer` on a human-addressed escalation.
   - The mutation "set `g.chief_cited_gate` for every rule, not only acknowledge" passed all 61 tests.
   - It would still need a valid cite, so this is not a bypass of the citation requirement. It does let the chief close a human gate through a route the design keeps closed.
   - Fix: add one request-level test for that call.

6. minor Spent citations are documented too narrowly (chief_cite.py module docstring; CLAUDE.md:747-749).
   - The docs say 404 or 409. Also spent are `text/plain` content type (the gate reads it with `force=True`, the route's strict `get_json()` gives 415 then 500) and `/comms/answer` on a human escalation (route 403).
   - A chief, buggy or hostile, can burn any unspent message of its session at no cost by naming a topic with no run or an idle run. The person is not told.
   - Fix: state that, in one sentence.
   - Related and undocumented: both timestamp sides use the wall clock, so a backwards clock step lets an older message pass.

7. minor chief_cite.py (acknowledge path): the chief chooses the `agent` field.
   - Probe: `POST /comms/acknowledge {"message_id": <human escalation>, "agent": "human", "cite": N}` as a chief gives 200 and `acknowledged_by == ["human"]`. The board then reads as if the person closed it, and the board is the stated mitigation.
   - Fix: require `agent == "chief"` on the cited acknowledge, as `/comms/post` requires `from == "chief"`.

8. minor Stale text left behind.
   - tests/http_api/test_chief_gate_keys.py:26: "Ticket 10 reads `cite` ... ahead of that". The gate reads it, so the `WAITS_FOR_A_TICKET` name is wrong for `cite`.
   - src/pathly_orchestrator/http_server/chief_field_calls.py:39: "(ticket 10 reads it)".
   - src/pathly_orchestrator/CLAUDE.md:397: the board-closure table still says an agent run's live token always gets 403 on a human-addressed escalation.
   - tests/http_api/test_chief_gate.py:455: the test name still says `meets_the_human_gate`.
   - src/pathly_orchestrator/CLAUDE.md:560: "can relay no answer until the tab is reopened" is too strong. After `/clear` a message recorded before it, for a question asked before it, can still be cited.

9. minor Tests that depend on the clock.
   - `later()` (tests/http_api/chief_cite_support.py) uses a 20 ms real sleep to order the clock. It is deterministic on Linux and I saw no flake across 3.12 and 3.13.
   - The Asker thread polls with `time.sleep` every 50 ms, bounded by a 5 s join.

REVIEW: FAIL
