# Stamp an answer the chief relays as chief-relayed

Type: task
Status: resolved
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/provenance_values.py, src/pathly_orchestrator/db/queries/comms_messages.py, src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py, src/pathly_orchestrator/http_server/chief_cite.py, tests/comms_board/test_chief_relayed_answer.py (new), tests/comms_board/test_comms_provenance.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/comms_board/INDEX.md

Spike 19 part B, proposed item S7: the answer a chief relays through `POST /comms/answer`
is stored `from_agent: human`, `author_source: none`; only `chief_citations` shows a chief relayed
it. With routed questions, the board now carries role answers (`author_source: token`, posted for consult runs)
beside the person's, and the person's relayed words must be told apart from an unverified post.

- `src/pathly_orchestrator/db/provenance_values.py`: new `SOURCE_CHIEF_RELAYED = "chief_relayed"`
  (the cited words of the person, relayed by the chief), added to `AUTHOR_SOURCES`.
- `src/pathly_orchestrator/db/queries/comms_messages.py::answer_question` takes optional keyword
  `author_role`, `author_run_id`, `author_source` and passes them to `post_message` (default:
  as today, stored `none`). The file is at 392 lines: keep it to the signature and the call.
- `src/pathly_orchestrator/http_server/chief_cite.py`: new `relayed_stamp() -> dict | None`,
  `{author_role: "chief", author_run_id: <the chief's run id>, author_source: chief_relayed}` when
  the gate let a cited chief answer through on this request (`g.chief_cited_text` is set and the
  caller's run token is the chief's), else None.
- `messages_crud.comms_answer` passes `relayed_stamp()` to `answer_question` when it is not None.
  The answer's text is still the cited message's (`answer_text`), and `from_agent` stays `human`
  (the words are the person's).

`runner/read_policy` treats any source but `none` as attributed, so a `chief_relayed` row is shown
to agents like a token-stamped one; `db/queries/comms_hydrate` turns a mirror row that claims it
into `legacy`, as it does every claimed source. Say both in `src/pathly_orchestrator/CLAUDE.md`
("Provenance").

`tests/comms_board/test_comms_provenance.py` pins `pv.AUTHOR_SOURCES` to the four values of round
one (its `_SOURCES` set): add `chief_relayed` to that set in place, keeping the test.

## Not in this ticket

- `/runner/agent-answer` (no board row) and the acknowledgement of a human escalation (no answer
  row): unchanged.
- An answer the person types in Studio (no token): stays `none`.

## Done when

- `python -m pytest tests/comms_board/test_chief_relayed_answer.py -q -p no:cacheprovider` passes
  and covers: a chief's cited `POST /comms/answer` stores the answer with `author_source`
  `chief_relayed`, `author_role` `chief`, `author_run_id` the chief's run, `from_agent` `human` and
  the cited text; a tokenless answer is stored `none`; an unknown source passed to `post_message`
  still raises `ValueError`; a mirror row claiming `chief_relayed` hydrates as `legacy`.
- All existing tests under `tests/comms_board` and `tests/http_api -k "chief_cite or chief_gate or answer"`
  still pass.

```check
$ python -m pytest tests/comms_board/test_chief_relayed_answer.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board -q -p no:cacheprovider
exit 0
$ python -m pytest tests/http_api -q -p no:cacheprovider -k "chief_cite or chief_gate or answer"
exit 0
```

## Reference

- `pathly/features/chief-agent/spike19-part-b-report.md` § Proposed tickets (7), § Surprises (read-only)
- `src/pathly_orchestrator/runner/provenance.py`, `src/pathly_orchestrator/runner/read_policy.py` (read-only)

## Answer

Work started at `0b52f4681d6b42f48c5a4b434d52653d784b7b3b` (HEAD at claim: `d80d548`, the merge of master on top of it). Test-only commit: `2c24670`.

- **Built**: `db/provenance_values.py` (`SOURCE_CHIEF_RELAYED = "chief_relayed"`, in `AUTHOR_SOURCES`); `db/queries/comms_messages.py::answer_question` (keyword-only `author_role`/`author_run_id`/`author_source`, forwarded to `post_message`; file now 399 lines); `http_server/chief_cite.py::relayed_stamp()` (+ one docstring sentence); `blueprints/comms/messages_crud.comms_answer` (passes `**(relayed_stamp() or {})`); `tests/comms_board/test_chief_relayed_answer.py` (new, 5 tests); `tests/comms_board/test_comms_provenance.py` (`_SOURCES` gains `chief_relayed`; the `comms_messages.py` allow-list comment now also says it forwards its caller's columns); `src/pathly_orchestrator/CLAUDE.md` (route table entry for `/comms/answer`, "Author provenance on board writes", the `provenance_values.py` tree line, the "No free re-runs" sentence); `tests/INDEX.md`, `tests/comms_board/INDEX.md` regenerated.
- **Proof**:
  - `python -m pytest tests/comms_board/test_chief_relayed_answer.py -q -p no:cacheprovider`: `5 passed`, exit 0 (at the test-only commit: 3 failed for the missing constant/function and the `none` stamp). Covers: a chief's cited `POST /comms/answer` stores `from_agent: human`, the cited text, `author_role: chief`, `author_run_id` the chief's run, `author_source: chief_relayed`; a tokenless answer stores `none`/None/None; `relayed_stamp()` is None for a chief token with nothing cited and for cited text with no chief token; `post_message(author_source="chief-relayed")` raises `ValueError`; a mirror row claiming `chief_relayed` hydrates as `legacy`.
  - `python -m pytest tests/comms_board -q -p no:cacheprovider`: `1577 passed`, exit 0.
  - `python -m pytest tests/http_api -q -p no:cacheprovider -k "chief_cite or chief_gate or answer"`: `1613 passed, 983 deselected`, exit 0; the full `tests/` suite afterwards on the final code: `6801 passed, 14 skipped`.
  - Lint: `black --check src/ tests/`, `mypy`, `check_file_size.py` (none new, none grown), `check_no_mirror_reads.py`, `gen_test_index.py --check`, `lint-imports` (1 kept), `bandit -ll`: all clean.
- **Decisions**: the chief's run id comes from the run token (`caller_identity(request)` + `is_chief_run`), never the body, and `author_role` is the token's role (`identity.role`, which `is_chief_run` has just checked is `chief`): the provenance scan `test_no_author_value_is_hard_coded_outside_the_db_constants` refuses an `author_*` string literal outside `db/`, and adding a `CHIEF_ROLE` constant was not needed. The token is resolved a second time (the gate does not keep its lookup on `g`), which keeps `chief_gate.py` out of the change. `relayed_stamp` imports `run_identity` and `provenance_values` lazily, as `chief_cite` does for its other db imports. `comms_messages.py` stays on `_UNSTAMPED_ALLOW` (its `post_message` forwards variables, which the scan reads as unstamped); no allow-list entry added.
- **Shortcuts taken**: none.
- **For later tickets**: an answer row with `author_source: chief_relayed` now carries the chief's run as `author_run_id` (a non-null run id on a `/comms/answer` row is new). `tests/comms_board/test_read_policy.py`'s own `SOURCES` list was not changed (not in Touches); `read_policy` needs no change since it only tests `== "none"`.
