# Refuse a consult run's own `answer` post

Type: task
Status: resolved
Blocked by: 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/consult_guard.py (new), src/pathly_orchestrator/http_server/app.py, tests/http_api/test_consult_answer_guard.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

Split from ticket 02. A `type: answer` post frees parked tasks the moment it is written
(`post_message` → `release_on_answer`), before the router measures what the consult changed, so a
consult agent must not deliver around the check (spec Decisions, "Where the answer comes from").
Ticket 02's skill tells it not to; this ticket makes it so.

New `src/pathly_orchestrator/http_server/consult_guard.py` (new): a `before_request` registered in
`src/pathly_orchestrator/http_server/app.py` after `run_token_guard` (search `run_token_guard`),
that answers 403 `{"error": "a consult answers in its completion summary; Pathly posts the
answer"}` to `POST /comms/answer`, and to `POST /comms/post` whose JSON body has `"type": "answer"`,
when the caller is a live run token whose run id starts `consult-` (resolve it the way `run_token_guard` does; imports lazy
inside the function). Every other post of a consult run passes (status, discovery, question), and
an answer from any other caller is unchanged. A body that is not JSON passes to the route, which
already refuses it.

Document the guard in `src/pathly_orchestrator/CLAUDE.md` beside the consult run.

## Not in this ticket

- Measuring the tree and withholding the router's own answer: the read-only check (spec Decisions).
- The other board writes a consult may make (`/comms/edit`, `/comms/supersede`): unchanged; they do
  not post an answer or free a parked task.

## Done when

- `python -m pytest tests/http_api/test_consult_answer_guard.py -q -p no:cacheprovider` passes and
  covers: a `POST /comms/post` `type: answer` and a `POST /comms/answer` with a consult run's token
  are each 403, store no row and free no parked task; a `status` and a `question` post with the same token are 200; an
  `answer` from a builder run token and from a tokenless caller are 200; a revoked consult token
  is refused by `run_token_guard` as today.
- All existing tests under `tests/http_api` and `tests/comms_board` still pass.

```check
$ python -m pytest tests/http_api/test_consult_answer_guard.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api tests/comms_board -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Where the answer comes from", "Consult run identity")
- `src/pathly_orchestrator/http_server/run_token_guard.py`, `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py` (`/comms/answer`)

## Answer

Work started at 9f0f1811956afcd632c3e8799dace515dd7ab813 (a tree-same merge of master on the conductor's base ffcebd2).

**Built**
- `src/pathly_orchestrator/http_server/consult_guard.py` (new): `consult_guard()`, a `before_request` that answers 403 `{"error": "a consult answers in its completion summary; Pathly posts the answer"}` to `POST /comms/answer`, and to `POST /comms/post` whose body (read with the comms `read_json_body`, the route's own decoder) has `"type": "answer"`, when the `X-Pathly-Run-Token` resolves (`resolve_run_token`, live rows only) to a run id starting `CONSULT_RUN_PREFIX` (`consult-`). All imports are lazy inside the functions.
- `src/pathly_orchestrator/http_server/app.py`: imports it and registers it right after `run_token_guard`, before `chief_gate` (196 -> 199 lines).
- `tests/http_api/test_consult_answer_guard.py` (new, 10 tests), `tests/INDEX.md`, `tests/http_api/INDEX.md` (regenerated).
- `src/pathly_orchestrator/CLAUDE.md`: an "Own answer refused (ticket 17)" bullet under the consult run's Result, and a `consult_guard.py` line in the http_server file tree.

**Proof**
- `python -m pytest tests/http_api/test_consult_answer_guard.py -q -p no:cacheprovider`: `10 passed`, exit 0. At the test-only commit 0170de5 it was `2 failed, 8 passed` (both consult answer cases got 200). Covered: consult `POST /comms/post` type answer and `POST /comms/answer` are 403 with the exact error, no `answer` row replying to the question, and the parked task stays `blocked` / `waiting_for_answer:<qid>`. Consult `status` and `question` posts are 200. An answer from a builder token and from a tokenless caller is 200 on both routes and frees the task (`pending`). A revoked consult token gets 401 `unknown run token` on all three posts. A non-JSON body reaches the route (400 `Missing or invalid JSON body`).
- `python -m pytest tests/http_api tests/comms_board -q -p no:cacheprovider`: `4193 passed in 1197.46s`, exit 0.
- Also: `check_file_size.py` OK (none new, none grown), `gen_test_index.py --check` up to date, `black --check`, `mypy` on the new file, `lint-imports` (1 kept, 0 broken), and `bandit -ll` on the new file are all clean.

**Decisions**
- The body is read with `read_json_body`, the same lenient decoder `/comms/post` uses, so a cp1252 body the route would store as an answer cannot slip past a stricter `get_json`.
- The token is checked only when the request posts an answer, and only `resolve_run_token` is used: a revoked or unknown token is already `run_token_guard`'s 401, so this hook never sees it.
- The guard goes before `chief_gate`. A consult token is never a chief token, so the order between them does not matter; putting it first keeps it next to `run_token_guard` as the ticket asks.

**Shortcuts taken**: none.

**For later tickets**: a consult test that wants an answer row must post it as the server does (`consult_stamp` through `post_message`, or a non-consult caller). A consult token on `/comms/post` type answer or `/comms/answer` now gets 403.
