# Prove the identity and provenance layer end to end, and update the living docs

Type: task
Status: open
Blocked by: 02, 07, 09
Test first: no

Write `tests/comms_board/test_rrp_acceptance.py`, the bar in map.md, driving the real pieces
together (no mocks of the code this plan built):

1. Spawn an FSM stage through `supervisor/terminal.py` with a fake broadcaster; read `run_token`
   from the `TERMINAL_SPAWN` payload; it resolves to the stage's run and role.
2. With that token as `X-Pathly-Run-Token`, `POST /comms/post` a `discovery` with `from: "explorer"`
   through the Flask test client: stored as `author_role=builder` (or the stage's role),
   `author_source=token`.
3. Post a second row with no header: `author_source=none`.
4. `resolve_read_policy(conn, "reviewer", feature)` and `policy_predicate` select neither the
   builder discovery nor the unverified row; `row_allowed` agrees on both; a `decision` posted by
   the builder is still selected.
5. After the spawn settles, the token resolves to `None`.

Then update the living docs in the same commit (root `CLAUDE.md`, "Documentation sync"):
`src/pathly_orchestrator/CLAUDE.md` (comms board: provenance columns, `run_tokens`, the
`X-Pathly-Run-Token` header, `runner/read_policy.py` existing but not yet wired), and root
`CLAUDE.md` if its comms-board paragraph names who may read what. Add a `CHANGELOG.md` entry.

Run the full suite and the Studio typechecks once here.

## Not in this ticket

- Withholding anything from any agent: a later plan (RRP-4 onward).

## Done when

- `python -m pytest tests/comms_board/test_rrp_acceptance.py -q` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.
- Both Studio typechecks exit 0.
- `python scripts/gen_test_index.py --check` exits 0.

```check
$ python -m pytest tests/comms_board/test_rrp_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
exit 0
$ python scripts/gen_test_index.py --check
exit 0
```

## Reference

- map.md "The bar"; SPEC.md § C1–C4
- Answers of tickets 01–09
- Root `CLAUDE.md` "Documentation sync", `src/pathly_orchestrator/CLAUDE.md`

## Answer
