# Let the chief answer an agent question only with the human's message id

Type: task
Status: open
Blocked by: 03
Test first: yes

`POST /runner/agent-answer` (`http_server/blueprints/runner/api_control.py`) supplies an answer
to a waiting stage. Today any caller can answer. Add a gate in a new
`http_server/blueprints/runner/_answer_gate.py` and call it from the route (SPEC.md § C2, § C4):

- caller with a `chief` run token → the body must carry `human_message_id`, naming a
  `chief_thread` row with `role="human"` in the token's project; otherwise `403` with a reason.
  The answer is posted to the board with the human's text quoted and the message id.
- caller with any other run token (builder, reviewer, …) → `403`: agents do not answer agents.
- caller with no token (the Studio UI today) → unchanged behaviour.

## Not in this ticket

- How the question reaches the chief: the inbox ticket.

## Done when

- `python -m pytest tests/http_api/test_chief_answer_relay.py -q` passes and covers: chief token
  with a valid human message id → answer delivered and the board post quotes it; chief token with
  no id, an unknown id, a `role=chief` id, or another project's id → `403`; builder token → `403`;
  no token → delivered as today.
- `api_control.py` does not grow by more than the call site.

```check
$ python -m pytest tests/http_api/test_chief_answer_relay.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C4 "Human-in-the-loop through the chief"
- `http_server/blueprints/runner/api_control.py` (`runner_agent_answer`), `db/queries/chief.py`
- Ticket 03's Answer

## Answer
