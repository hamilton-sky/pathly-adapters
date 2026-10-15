# Audit-log every executed operator action

Type: task
Status: resolved
Blocked by: 03
Test first: yes

Every tool the operator executes (post-confirmation) is recorded:

- Where: a board message stamped `actor: local-operator` on the
  relevant board (reuse the comms post path ticket 02 mapped for
  `post_message`, with the actor stamp distinguishing it from human
  and chief messages), OR a dedicated lightweight log if the board
  is the wrong home — decide in the Answer, one paragraph.
- What: `{tool, args, result_summary, ts, confirmed_by: "chat"}`.
  Results are summarized (one line), never full payloads.
- The audit write itself never goes through the model — the loop
  writes it directly after a successful API call.
- Reads and cancelled proposals are NOT logged (noise); only
  executed mutations.

## Not in this ticket

- A UI surface for browsing the audit log: the board messages are
  the surface in v1.

## Done when

- `python -m pytest tests/local_operator/test_audit.py -q -p no:cacheprovider` passes and covers: an executed `retry_stage` produces exactly one audit record with the settled fields; a cancelled proposal produces none; a read-only turn produces none.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/local_operator/test_audit.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Stories ("Small hands by construction"), § Interfaces
- Ticket 02's `post_message` mapping (the post path to reuse)

## Answer

Resolved 2026-10-14. Home: **the board** HQ was answering about — one
`status` post from `local-operator` per EXECUTED action (done or failed),
server-written with the system provenance stamp, so it can't be confused
with the human or the chief and is never written by the model. The board is
where people already look for what happened, and agents read it as recent
events; a separate log would be a second place nobody watches.

Text: `⚡ HQ operator · <tool> {args} → done|failed: <one-line result> ·
confirmed in chat` — args without paths or payloads; `ts` is the
message's own. Written by `/hq/actions/run` after the route returns
(server-run) or `/hq/actions/report` (Studio-run diagrams). Proposals,
cancels, stale/unavailable cards and read-only turns write nothing.
`blueprints/hq/_action_audit.py`.

`tests/local_operator/test_audit.py` (4 tests) green: an executed
`retry_run` writes exactly one record with the settled fields; a failed
execution is recorded as failed; cancel / stale / read-only and operator
turns write none; Studio-run actions are audited on report and a
server-run one can't be "reported". `check_file_size.py` OK.
