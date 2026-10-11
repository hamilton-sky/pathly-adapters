# Add the episodic memory tier: one embedded episode per finished run, read behind the role wall

Type: task
Status: open
Blocked by: —
Test first: yes

SPEC.md § C3 and role-read-policy SPEC § C8.

- `db/migrations_memory.py` (`add_memory_episodes(conn)`, called from
  `migrations_incremental`) and `db/queries/memory_episodes.py`: table `memory_episodes(id PK,
  project_root, feature, goal_id, run_id, role, outcome, summary, ts, author_role, author_run_id,
  author_source, type TEXT DEFAULT 'episode')` and a vec index created the same way comms
  embeddings create theirs (only when sqlite-vec is available; keyword fallback otherwise).
- `runner/memory_episodic.py`:
  - `record_episode(conn, run)` at run end, from the run's `AGENT_DONE.summary` and outcome;
    provenance comes from the run's token identity (`token`) or `system`, never from the summary.
    Embedded through `runner/embeddings.py`. Called where the run is settled (one line).
  - `retrieve_episodes(conn, role, feature, k, caller_run_id)`: resolves the role's policy with
    `resolve_read_policy` and ANDs `policy_predicate` into the query **before** `k`
    (fetch-until-`k` for the vector arm). An episode counts as type `discovery` for the policy, so
    the reviewer wall withholds the builder's episodes.
- `runner/comms_context_memory.py` renders an "Earlier runs" section; `runner/comms_context.py`
  gains one call site (the file is 394 lines).
- Extend role-read-policy's invariant test to enumerate this query.

## Not in this ticket

- Promotion of lessons: the scheduled-promotion ticket.

## Done when

- `python -m pytest tests/comms_board/test_memory_episodic.py -q` passes and covers: a finished
  builder run on feature X records one episode with `author_role=builder, author_source=token`; the
  next builder run on X sees it in its context; a reviewer run on X does not; the chief does; with
  five builder episodes ranked above one architect episode, a reviewer `k=5` read returns the
  architect episode.
- The read-path invariant test still passes with the new query enumerated.

```check
$ python -m pytest tests/comms_board/test_memory_episodic.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- SPEC.md § C3; role-read-policy `SPEC.md` § C3, § C8
- `runner/read_policy.py`, `runner/embeddings.py`, `db/queries/comms_embeddings.py` (vec setup)

## Answer
