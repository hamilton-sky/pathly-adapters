# BUILD HANDOFF PROMPT — state-one-authority

Paste the block below into a **fresh Claude Code session** (working dir
`C:\Users\Yafit\pathly-adapters`) to build this feature's 3 goals / 10 tasks. The design +
plan are DONE and live on the board (`SPEC` · `AUDIT_MIRROR_READS` · `ARCHITECTURE_PROPOSAL` ·
`IMPLEMENTATION_PLAN` · `DESIGN_NOTES`); this prompt drives the **build**, gated per goal.

Every builder/agent connects to the board through **Pathly fragments** (board context + the
task's `context_refs` + code intelligence) — either auto-composed by the runner, or replicated
explicitly when building directly (see the *USE PATHLY FRAGMENTS* section).

````text
Implement the `state-one-authority` feature — make Pathly's SQLite DB the single runtime
authority for state/events/artifacts and every disk file a one-way export (docs/
ARCHITECTURE_ONE_AUTHORITY.md Issue #4). The design + plan are DONE and live on the Pathly
board and on disk; your job is to BUILD it, gated per goal.

SETUP
- Repo: C:\Users\Yafit\pathly-adapters. Work on the EXISTING branch `dogfood/state-one-authority`
  (`git checkout dogfood/state-one-authority`; confirm `git branch --show-current`). Never commit
  to master, never push.
- Confirm the FSM server: `curl -s http://127.0.0.1:8765/health`. If down, start it, then continue.

READ FIRST (full spec, per-task prompts, verified blast-radius, diagrams):
- pathly/features/state-one-authority/ARCHITECTURE_PROPOSAL.md   (authoritative design)
- pathly/features/state-one-authority/IMPLEMENTATION_PLAN.md     (final ```json BOARD_DAG block =
  every task's exact prompt, Files, Done-when)
- pathly/features/state-one-authority/AUDIT_MIRROR_READS.md · SPEC.md · DESIGN_NOTES.md

THE WORK — 3 goals on the board (scope `state-one-authority`), RUN IN ORDER G1 -> G2 -> G3.
List tasks: curl -s "http://127.0.0.1:8765/comms/tasks?feature=state-one-authority&board=feature&scope=state-one-authority"
- G1 EVENTS/ARTIFACTS authority cutover: event-mirror-export -> retire-events-dual-write; drop-artifacts-jsonl
- G2 Studio -> DB read migration: split-db-api-explorer -> studio-data-layer-migration -> studio-planboard-migration
- G3 Enforce + cleanup: ci-mirror-read-gate, delete-test-only-write-state, fix-docstrings-and-claude-md-classification, migrate-cli-back-py (optional)

USE PATHLY FRAGMENTS (board context + code intelligence — do NOT run bare agents)
Fragments (core/skills/fragments/) are the layer that wires every agent to the board. Each
builder/architect you run must get: board context, the task's curated context_refs, and code
intelligence — the Pathly way.
- PREFERRED — let Pathly compose the fragments for you: run each task through the real runner
  (Studio "Run" on the goal, or `POST /comms/tasks/run {"message_id":"<task id>",
  "project_root":"C:/Users/Yafit/pathly-adapters"}`). The runner spawns the builder with the
  `development/build` skill + its fragments already composed — board-context (governance +
  referenced context_refs + semantic + catalog), code-query, comms-post, progress-logging,
  completion-report — so board context + code intel come for free. (Runner spawns need the Studio
  app as PTY host.)
- IF you build directly in this session, REPLICATE those fragments for EVERY builder/architect
  subagent you spawn (never a blank-slate agent):
   1. board-context fragment -> pull the exact block Pathly injects:
      POST http://127.0.0.1:8765/comms/agent-context/preview
        {"scope":"state-one-authority","board":"feature",
         "project_root":"C:/Users/Yafit/pathly-adapters",
         "task_description":"<the task's text>","task_id":"<task message id>"}
      Put the returned `block` at the top of the subagent's prompt.
   2. context_refs (already curated on each task -> the ARCHITECTURE_PROPOSAL sections it needs):
      hydrate with GET http://127.0.0.1:8765/comms/artifacts/<artifact_id>/section?... and include them.
   3. code-query fragment -> POST http://127.0.0.1:8765/code/query
        {"op":"impact","target":"<file>","role":"builder",
         "project_root":"C:/Users/Yafit/pathly-adapters","scope":"(interactive)"}
      on the files you'll touch; include the result.
   4. Spawn the builder/architect WITH (board block + context_refs + code-intel) in its prompt.
   5. comms-post + progress-logging + completion-report -> post status as you go
      (POST /comms/post type=status) and complete the task (POST /comms/tasks/complete) at the end.

RULES
1. ORDER MATTERS. Cross-goal deps are preconditions, not DAG edges (get_ready_tasks resolves
   depends_on only within a goal). Finish G1 fully, then G2, then G3. Within a goal, respect each
   task's depends_on.
2. ADDITIVE-FIRST. In G1, `event-mirror-export` is purely additive (new event_mirror.py + one call
   in eventlog.append_event) — land and verify it BEFORE `retire-events-dual-write` removes the
   agent write. Never leave a gap where events aren't written.
3. Implement one task's scope (its Files), then VERIFY its Done-when — run it, don't trust it:
   - Python: `python -m pytest tests/ -q` stays green.
   - Studio: `cd studio && node_modules/.bin/tsc --noEmit -p tsconfig.web.json` — redirect to a
     file and echo the exit code; never pipe to tail (masks the exit code).
4. After editing any core skill/fragment (G1 retire-events-dual-write, drop-artifacts-jsonl): run
   `pathly-setup claude --apply --repair` then `python -m build` (adapter sync — never hand-edit an
   adapter _meta file).
5. The CI gate (G3 ci-mirror-read-gate) runs LAST — only after every G1 + G2 task is done. If a
   precondition isn't met, STOP and report blocked; do NOT widen the allow-list to force a green.
6. Mark progress on the board: get a task's message_id from the /comms/tasks query (match by
   `slug`) and POST /comms/tasks/complete {"message_id":"<id>","feature":"state-one-authority"}.
7. Keep living docs in sync in the SAME commit (that IS G3 fix-docstrings-and-claude-md-classification).
8. Commit per GOAL on the branch (not per task). STOP and summarize after each goal for review
   before the next. Do not push.

Start: read the artifacts, confirm branch + server, pull board context for G1's first task
`event-mirror-export` (step 1 above), then build it.
````

## Two ways to run it
- **Direct (self-contained):** a fresh Claude Code session implements the tasks, replicating the
  fragments per the section above. No Studio needed.
- **True headless Pathly runner:** open **Studio**, press **Run** on each goal in order (executors
  are preset team/loop/single) — fragments auto-compose. Requires the Studio app as the PTY host.

Whichever way: keep the **per-goal review gate**, start with the additive `event-mirror-export`,
and never let it drain all three goals unattended (it edits Pathly's own state layer).
