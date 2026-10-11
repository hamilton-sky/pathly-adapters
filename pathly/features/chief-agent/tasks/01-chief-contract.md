# Add the chief role contract, its three fragments and its adapter metadata

Type: task
Status: open
Blocked by: —
Test first: yes

Create the chief role (SPEC.md § C2) without any server code:

- `src/pathly_data/core/agents/support/chief.md`: the role contract. It absorbs
  `director.md`'s routing (rigor choice, which executor) so the human has one front door, and
  states that the chief never edits project files and never runs a stage.
- `src/pathly_data/core/skills/fragments/chief-tools.md`: the only calls the chief makes, each a
  `curl` to `http://127.0.0.1:8765` with `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"`:
  `POST /comms/goals/decompose`, `POST /comms/goals/run`, `POST /comms/goals/stop`,
  `GET /comms/goals`, `GET /runner/status`, `GET /runs`, `POST /runs/<id>/<action>`,
  `POST /runner/agent-answer`, `POST /comms/post`, `POST /comms/search`, plus
  `POST /chief/reply` (added in ticket 04) to answer the human.
- `chief-rules.md`: never answer an agent or approve a decision for the human unless the human
  said so in this thread, and then pass the human message id; ask before stopping a run or
  starting a `strict` goal; post a decision as `binding` only when the human asked for a rule
  that all workers must follow.
- `chief-status.md`: answer status from goal rollups and run summaries, cite board ids, never
  paste raw status streams.
- `chief.yaml` in `src/pathly_data/adapters/{claude,codex,copilot,antigravity}/_meta/`, modelled
  on each adapter's `director.yaml`, with tools limited to `Bash` (for `curl`), `Read`, `Glob`,
  `Grep`; no `Edit` or `Write`.

## Not in this ticket

- Composing and spawning a chief turn: ticket 04.
- The `chief` read-wall row: role-read-policy ticket 01 already added it.

## Done when

- `python -m pytest tests/install_skills/test_chief_contract.py -q` passes: composing the chief
  role yields a prompt that contains every endpoint above with the run-token header, contains the
  three rules, and for the claude adapter lists no `Edit` or `Write` tool.
- `python scripts/check_adapters.py` exits 0.
- role-read-policy's fragment test (every `8765/comms` curl sends the token) still passes.

```check
$ python -m pytest tests/install_skills/test_chief_contract.py tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_adapters.py
exit 0
```

## Reference

- SPEC.md § C2; `src/pathly_data/core/agents/director.md` (routing to absorb)
- `src/pathly_data/CLAUDE.md` (core → adapter stitching), `src/pathly_data/adapters/*/_meta/director.yaml`
- `tests/install_skills/test_board_search_fragment.py` (pattern for a fragment test)

## Answer
