# SPEC — Role Read Policy (builder ≠ reviewer on the board)

_Draft plan. Follow-up to the blackboard assessment
([`ASSESSMENT.md`](../../project/explorations/blackboard-architecture-assessment/ASSESSMENT.md)),
ISSUE-1 in particular. Every claim in §A was read against code at `84da619`; file:line refs are
from that commit._

> **Thesis.** The board already separates knowledge **by tier** (feature → project → global) and
> **by feature**, and it gates **writes** by role on the server. What it does not do is separate
> knowledge **by role on reads**: a reviewer reads everything the builder wrote, including the
> builder's reasoning, and any agent can pull any board through `/comms/search` or `GET /comms`.
> So "independent review" is a prompt-level hope, not a board property. This spec makes it one.

---

## A. What exists today (verified)

| Axis | What it does | Enforced where |
|---|---|---|
| **Tiers** feature/project/global | Reads **aggregate** across tiers; own board gets the lenient cutoff, cross-tier rows must clear `{feature 0.75, project 0.55, global 0.50}` | push path only — `runner/comms_context.py:33`, `:151-227` |
| **Per-feature isolation** | A feature board is the `(board="feature", scope=<feature>)` pair; a run reads only its own feature board | push path only |
| **Write gate by role** | feature: anyone; project: `_PROJECT_WRITERS`; global: director/evaluator/human | **server** — `http_server/blueprints/comms/_helpers.py:127` |
| **Upward promotion** | copies only `decision`/`constraint`, strictly upward, with provenance | **server** — `db/queries/comms_promote.py` |
| **Per-role read** | a per-role `board_scope` row toggles **which tiers** a role reads and how many rows | push path only — `db/queries/app_settings.py:51`, `runner/board_scope.py:33` |

Three gaps follow from the table:

1. **Per-role read is a tier switch, not a content filter.** The `board_scope` value is
   `{feature, project, global}` booleans (+ per-tier k). Nothing filters by message **type** or by
   **author** (`from_agent`). On one feature board the reviewer and the builder see the same rows.
2. **No built-in per-role default.** `get_board_scope` says so deliberately (`app_settings.py:62`):
   without an explicit row every role falls through to the feature row → all tiers. In practice
   every role reads the same thing.
3. **Pull paths are unguarded.** The `board-search` fragment tells agents to call
   `POST /comms/search`; that route (`messages_crud.py:62`) and `GET /comms` (`:15`) accept any
   `board`/`scope` from the body and never check the caller's role, tiers, or feature. A builder on
   feature A can read feature B's board, and a reviewer can pull the builder's discoveries even if
   the push path had filtered them.

**Why it matters.** Adversarial review is only adversarial if the reviewer judges the *artifact*
(spec + diff + decisions), not the builder's *story about* the artifact. A reviewer primed with the
builder's `discovery`/`status` posts tends to agree with them — the anchoring problem the review
stage exists to break.

---

## B. Goals / non-goals

**Goals**
- G1. A role's reads can be filtered by **type** and **author role**, not only by tier.
- G2. Sensible **built-in defaults** for `reviewer` and `tester` (an information wall from builder
  reasoning), overridable per project/feature/role.
- G3. The **same policy** applies on all three read paths: push (`retrieve_board_context`),
  `POST /comms/search`, `GET /comms`.
- G4. Reads are bound to the **intended `(board, scope)` pairs** for a run (closes ISSUE-1 on the
  read side, including cross-feature pulls).
- G5. Filtering is **visible**: the context preview and the per-run context record say what was
  withheld and why.

**Non-goals**
- Changing write permissions or promotion (already server-enforced).
- Verifying the *truth* of feature-tier posts (an "unverified discovery" state is a follow-up).
- Filesystem/Git isolation between stages (ASSESSMENT §0 — a separate, larger problem).
- Restricting the human / Studio UI: reads carrying the UI token stay unrestricted (C4).

---

## C. Design

### C0. Threat model — what the wall can and cannot stop

The risk this spec targets is **anchoring**: a cooperative reviewer that reads the builder's
narrative and stops looking. It is not a hostile agent working to defeat the wall, and no
HTTP-level control could stop one. Headless agents run with shell and filesystem access
(`--dangerously-skip-permissions`, `cwd=project_root`), so an agent that wants the builder's posts
can read `~/.pathly/pathly.db` with `sqlite3`, or the `BOARD.json` exports on disk, without
touching `/comms/*`.

So the design goals are:
- every path an agent uses **by default** (the injected context and the fragment `curl`s) shows
  only what its role may see, and no path it is told about can be unlocked by dropping or
  changing a request field;
- going around the wall is **visible**: unauthenticated agent-style calls are counted (C5).

Making a reviewer unable, rather than unlikely, to see the builder's posts would need process
isolation (no DB or board-export access from the agent sandbox). That is out of scope; see §F.

### C1. Policy shape

Extend the per-role `board_scope` value with two optional keys. Absent keys = today's behaviour,
so existing rows keep reading exactly what they read now.

```json
{
  "feature": true, "project": true, "global": true,
  "exclude_types": ["discovery", "status", "nudge"],
  "exclude_authors": ["builder"]
}
```

- A row is withheld if `type ∈ exclude_types` **and** (`exclude_authors` is empty **or**
  the row's **trusted author role** `∈ exclude_authors`). Both lists together mean "this kind of
  post *from these roles*", which is the precise wall we want (a reviewer still sees a
  `discovery` from the explorer or the architect).
- **The author role is not `from_agent`.** `/comms/post` copies the caller's `from` field
  straight into `from_agent` (`messages_write.py:56`), and feature-board writes accept any value
  (`_helpers.py:127`), so a builder could label a discovery `explorer` and walk it through the
  wall. The policy keys on a new `author_role` column, stamped **by the server at write time**
  from the caller's run token (C4), never from the body: a `run_id` in the body is as
  self-reported as `from`. Rules:
  - post with a valid run token → `author_role` = that run's role, whatever `from` says;
  - server-internal writers (`supervisor`, `system`, e.g. `goal_verify.py:106`,
    `task_retry.py:176`) → stamped as `system` by the code path, not by a body field;
  - no run token → `author_role = NULL` ("unverified"). For a role with `exclude_authors` set, an
    unverified row of an excluded type is **withheld** (fail closed), and counted as
    `unverified` in C7, so the wall cannot be bypassed by dropping the token. Human posts from
    the UI are not affected: humans post `decision`/`constraint`/goals, which are never withheld.
  - the same write also stamps `author_run_id` from the token. The existing `run_id` column is
    filled from the request body (`messages_write.py:127-132`), so it is not provenance; the
    policy never reads it.
- **Rows written before the upgrade.** A migration adds `author_role`, `author_run_id` and
  `author_source ∈ {token, system, legacy, none}`. Fail-closed applies only to `none` (a row
  written *after* the upgrade without a token). Existing rows are backfilled as `legacy`, with a
  best-effort role, so history is not wiped from every reviewer's view:
  - `from_agent ∈ {supervisor, system}` → `system`;
  - else, if the row's `run_id` joins an `agent_invocations` row (written after each run
    finished, `db/migrations.py:71`) → that invocation's `agent_role`;
  - else → `from_agent` as stored.

  `legacy` roles are as spoofable as `from_agent` always was. The policy applies them as
  written, and C7 counts `legacy` separately, so the soak (P6) shows how much history a reviewer
  still sees on unverified attribution before `enforce` is switched on.
- **Never withheld, whatever the policy:** governance (pending decisions, active escalations),
  `decision`, `constraint`, `goal`/`task` rows, and the run's own posts, meaning rows whose
  server-stamped `author_run_id` equals the caller's token run (never the body `run_id`, which
  a builder could set to the reviewer's run to make a discovery visible). Governance is injected
  unconditionally today ("always applies — do not override"); a read policy must not be able to
  hide a pending decision from the agent that has to respect it.

Resolution order is unchanged: per-role row → per-feature row → built-in role default → all.
The new step is the **built-in role default**, which today does not exist by design
(`app_settings.py:62`). Adding it is a deliberate behaviour change — see §F, open question 1.

### C2. Built-in defaults

| Role | exclude_types | exclude_authors | Rationale |
|---|---|---|---|
| reviewer | discovery, status, nudge, warning | builder | judge the diff + spec, not the builder's narrative |
| tester | discovery, status, nudge | builder | acceptance criteria are the oracle, not the build log |
| chief | status, nudge, discovery | — (any author) | keep the long-lived chief's context lean; see C8 |
| everyone else | — | — | unchanged |

`warning` is withheld from the reviewer only when authored by the builder: a builder warning
("this path is untested") is exactly the hint that steers a reviewer away from a real defect.
Up for debate in review of this spec.

### C3. One policy function, three read paths

One policy, applied **inside the query, before `k`/`limit`**, on all three read paths:

1. `retrieve_board_context` — semantic and recency-fallback rows.
2. `POST /comms/search`.
3. `GET /comms`.

**Filter before truncating, not after.** All three paths are bounded (`k` on search, `limit` on
`GET /comms`, `k + over_fetch_margin` on the push path, `comms_context.py:171`). Filtering the
bounded window afterwards can empty it while permitted matches sit just below: five top-ranked
builder discoveries followed by an architect discovery would give a reviewer `k=5` search
nothing. So the policy compiles to a SQL predicate,
`runner/read_policy.py::policy_predicate(policy) -> (where_sql, params)`, which the comms read
queries (`search_by_keyword`, `search_by_embedding`, `search_by_hybrid`, `get_messages`) AND into
their `WHERE` before ranking and `LIMIT`. Where a query cannot take a predicate (e.g. the
vector-distance arm), it **fetches until `k` permitted rows are found or the candidates run out**,
never a single fixed over-fetch.

The predicate is generated from one place, and a pure `row_allowed(row, policy)` twin exists only
for tests and the `warn`-mode counters (C5), with a test that the two always agree. Keeping it
one source is the point: the assessment's through-line is "trusted, not enforced", and three
hand-copied filters drift.

### C4. Who is asking — run identity on pull paths

The pull routes cannot apply a role policy without knowing the caller's role.

- **Callers are identified by a spawn-issued token, not by a request field.** At spawn the
  supervisor mints a random per-run token and records `token → run_id → (role, feature,
  project_root, board, scope)`. The spawn host puts it in the agent's environment as
  `PATHLY_RUN_TOKEN`, next to `PATHLY_GATE_BILLED`, which `studio/src/main/ipc/terminal.ts:179`
  already sets for runner tabs (and the same in `pathly-pty-host`). The `board-search`,
  `board-init` and `comms-post` fragments send it as a header (`X-Pathly-Run-Token`). A
  `run_id` or `role` in the body is ignored for policy purposes, so a reviewer cannot ask as
  `human` or as another run. The same token stamps `author_role` on writes (C1).
- **The UI is identified through its own channel too.** The existing `X-Pathly-Secret` cannot
  be that channel: it lives in `~/.pathly/server_secret.txt`, which agents can read, Studio main
  copies it into `process.env` (`studio/src/main/apiConfig.ts:29`) where spawned processes
  inherit it, and the middleware already lets loopback callers without it through
  (`http_server/middleware.py:168-180`). So a separate **UI token**:
  - minted by the server at startup and handed to Studio main (file or handshake, the build
    picks one), **never** written into `process.env`, so spawned agents do not inherit it;
  - exposed to the renderer through the preload bridge, next to the secret that
    `window.pathly.shell.apiConfig()` already returns;
  - sent as `X-Pathly-UI-Token` by the renderer's `apiFetch` wrapper
    (`studio/src/renderer/src/lib/config.ts:17`). Every board read the UI makes goes through
    that one wrapper (`store/commsApi/messages.ts:15`, `search.ts:14`), so it is the place to
    add it; main-process calls add it too;
  - added to the CORS `Access-Control-Allow-Headers` lists (`middleware.py:162`, `:213`), or
    the browser preflight drops it.

  Per C0, an agent that goes looking for the token file can still read it; the goal is that no
  agent has it by default.
- **No token at all = anonymous, not unrestricted.** In `enforce`, a request with neither token
  gets the `anonymous` policy, which defaults to the **union of the built-in walls** (C2). Dropping
  the header therefore never shows more than the strictest role sees. Scripts and interactive
  `/pathly` CLI use that need everything can be given a token explicitly.
- **Open item:** `agent_invocations.agent_role` (`db/migrations.py:77`) is a projection of
  `AGENT_DONE`, so it is written *after* the run, too late for mid-run reads. The build must find
  or add a record written at spawn (the supervisor knows role + scope when it composes the prompt;
  `supervisor/task_prompt.py`, `supervisor/board_run.py:342`).

### C5. Enforcement modes (rollout safety)

`read_policy.mode` setting: `off` | `warn` | `enforce`. Default `warn`.

- `warn`: compute the policy, return everything, and log + count what *would* have been
  withheld (and any cross-pair read, C6). Ships first, so real runs show the impact before
  anything is hidden.
- `enforce`: withhold.
- In both modes, requests without a valid token are counted and logged with their caller
  details, so going around the wall shows up in the run record instead of passing silently.

### C6. `(board, scope)` pair binding (ISSUE-1, read side)

- With a resolved run, a pull request may only target the pairs the run is entitled to:
  `search_tiers_value` (`runner/board_scope.py:47`) already renders exactly that set. A request
  for another pair (e.g. another feature's board) is refused in `enforce` (see below for the
  structural-lookup exception and the error shape) and counted in `warn`.
- **Structural lookups are not bound to the current pair.** `board-init` deliberately reads
  *other* feature boards: when a run creates features it looks up each new feature's root goal
  (`GET /comms?feature=<f>&scope=<f>&type=goal`) and posts one only if none exists. Binding that
  read to the run's own pair would make every lookup come back empty in `enforce`, and the
  fragment would post a duplicate root goal per feature. So reads restricted to structural rows
  (`type ∈ {goal, task}`) on **any feature board** are always allowed. They carry no agent
  reasoning, and `goal`/`task` rows are never withheld anyway (C1). Anything else on a foreign
  pair is refused.
- **Why not "feature boards of the same project".** That would need ownership data the board
  does not have: `comms_messages` is keyed by `(board, scope)` with no `project_root` column
  (`db/migrations.py:287`), the DB is global (`~/.pathly/pathly.db`), and `board-init` runs its
  lookup *before* the new feature has any row from which a project could be inferred. Feature
  boards are therefore not project-qualified today: two projects with a feature of the same name
  already share one board for every read and write. That is a pre-existing identity problem, not
  one this spec introduces or can fix with a read rule; see §F, question 5.
- A refusal is an **HTTP error** (`403` + `reason`), never `200 []`. Fragments that branch on
  "nothing found" (as `board-init` does) must be able to tell "refused" from "empty", or they act
  on a false negative.
- Add a query helper that **requires** both `board` and `scope` and use it in the comms read
  queries, as ASSESSMENT ISSUE-1 proposes.

### C7. Visibility

- `record_board_context` / `render_stats` (`runner/context_record.py`) gain a `withheld` count
  per reason (`type`, `author`, `unverified`, `pair`), plus how many rows were shown on a
  `legacy` attribution.
- The context preview (`POST /comms/agent-context/preview`, `blueprints/comms/context.py`) already takes
  `role`; it shows withheld rows greyed with the rule that hid them, so a human can see the wall.

### C8. Future read paths must go through the same predicate

This spec walls the three read paths that exist today. Two planned features add more, and
each one would reopen the wall if it read the comms tables (or anything derived from them)
on its own:

- **Memory tiers** ([`chief-agent/SPEC.md`](../chief-agent/SPEC.md) §C3). An episodic tier
  (embedded run summaries) and a semantic tier (promoted lessons) are new retrieval sources
  injected next to `retrieve_board_context`. A run summary written by the builder is the
  builder's narrative in another table, so a reviewer must not get it through memory when
  the board would withhold it. **Rule:** every memory record carries the same provenance
  columns (`author_role`, `author_run_id`, `author_source`, C1), stamped from the run token
  at write time, and every memory read ANDs `policy_predicate` into its query before `k`,
  the same as C3.
- **The chief agent** ([`chief-agent/SPEC.md`](../chief-agent/SPEC.md)). The chief is a
  role like any other: it gets a run token (C4) and a built-in default (C2 gains a `chief`
  row). Its wall exists to save context, not to prevent anchoring: it reads decisions,
  constraints, goals/tasks, escalations, pending interactions and run summaries, and not
  every `status`/`nudge`/`discovery` post. Default:
  `exclude_types: ["status", "nudge", "discovery"]`, `exclude_authors: []` (all authors).
  It can still pull a specific row by id when it needs one.

**Provenance before promotion.** `/comms/promote` and `/comms/consolidate` will be scheduled
automatically by the memory work. Promotion to `global` must then require
`author_source ∈ {token, system}` (not `legacy`/`none`) plus evaluator or human approval, so
a spoofed or unverified post cannot become a lesson injected into every future prompt. This
reuses P2's columns; nothing new in this spec.

---

## D. Phases (each → one board task)

| # | Phase | Priority | Risk | Done when |
|---|---|---|---|---|
| P1 | Policy shape + `policy_predicate` / `row_allowed` + built-in defaults, unit-tested | P0 | Low | tests cover every rule in C1/C2, incl. governance never withheld; predicate and `row_allowed` agree on every case |
| P2 | Server-stamped `author_role` / `author_run_id` / `author_source` on every write (from the run token; `system` for internal writers; `none` = unverified) + migration that backfills existing rows as `legacy`. Needs P3's token, so build P3's token half first | P0 | Med | a post with `from: explorer` under a builder token is stored as `author_role=builder`; a body `run_id` changes nothing; migrated rows carry `legacy` roles |
| P2b | Wire the predicate into the push path (semantic + recency) in `warn`, before `k` | P0 | Low | context record shows withheld counts; prompt unchanged in `warn` |
| P3 | Spawn-issued run token (env → header) + UI token (preload bridge → renderer `apiFetch`, not in spawn env) + `anonymous` policy on `/comms/search` and `GET /comms`; fragments send the token | P0 | Med | a reviewer-token search returns the filtered set; body `run_id`/`role` ignored; the same call with no token returns no more than the strictest wall |
| P4 | `(board, scope)` pair binding on pull routes + required-pair query helper | P1 | Med | cross-feature content pull → `403` + reason in `enforce`; `board-init` goal lookup on a new feature still works; invariant test over all comms reads |
| P5 | Preview + Studio visibility of withheld rows | P1 | Low | preview for `role=reviewer` shows what is hidden and why |
| P6 | Flip default to `enforce` after a `warn` soak on real runs | P1 | Med | soak data reviewed; no review stage starved of needed context |

**Sequencing with the chief agent.** P1–P3 are also the identity layer the chief agent and the
memory tiers build on (run token, server-stamped `author_role`, one predicate). So the order is:
P1–P3 here (the feature-flow plan in `tasks/`) → the whole chief-agent feature-flow plan, started
in the next session as soon as this one reaches DONE → P4–P6 here as a later plan. Building the
chief first would give it a pre-token identity that P3 then has to retrofit.

P1–P3 are the minimum that makes the wall hold on every default path and for every request an
agent can shape (C0); none of them stops an agent that reads the DB file directly. P4 closes
the cross-feature leak.

---

## E. Tests

- Unit (`row_allowed` + `policy_predicate`): type-only, author-only, type∧author, empty lists,
  governance and `decision`/`constraint` always kept, own-run posts kept, unknown role → no
  filter, unverified author of an excluded type withheld; the SQL predicate and `row_allowed`
  agree on every case.
- Author stamping: `from: "explorer"` posted under a builder token is stored and filtered as
  `builder`; a body `run_id` naming the explorer's run changes nothing; a post with no token is
  `author_role = NULL`, `author_source = none`.
- Own-post exemption: a builder discovery posted with the **reviewer's** `run_id` in the body
  stays hidden from that reviewer; the reviewer's own posts stay visible.
- Legacy backfill: on a DB migrated from before the upgrade, an explorer discovery whose
  `run_id` joins an explorer invocation is `legacy`/`explorer` and visible to a reviewer; a
  `supervisor` status is `legacy`/`system`; a builder discovery is hidden.
- UI token: a renderer board read through `apiFetch` carries `X-Pathly-UI-Token` and gets the
  unrestricted view in `enforce`; a spawned agent's environment contains no UI token.
- Truncation: five top-ranked builder discoveries + one architect discovery, reviewer search
  with `k=5` → returns the architect row (the filter runs before `k`); same on the push path.
- Resolution: per-role row beats built-in default; explicit row with no `exclude_*` keys reads
  as today (back-compat).
- Push path: reviewer context for a board seeded with builder `discovery` + architect `discovery`
  + a pending decision → only the latter two appear (in `enforce`); all three in `warn` with a
  withheld count of 1.
- Pull path: same seed via `/comms/search` with a reviewer token; body `role: "human"` or another
  run's `run_id` does not lift the filter; no token → `anonymous` policy (in `enforce`, no more
  than the strictest wall), and the call is counted; a UI-token call is unrestricted.
- Pair binding: a feature-A run searching `board=feature, scope=B` → `403` + reason in
  `enforce`; counted in `warn`. A `board-init` lookup `GET /comms?scope=<new>&type=goal` from
  the same run is allowed, and no duplicate root goal is posted.
- Recency fallback (no embedding) filtered the same as the semantic path.
- Invariant (C8): every query that reads `comms_messages`, or a memory table derived from it,
  goes through `policy_predicate`. A test enumerates those queries, so a new read path that
  skips the predicate fails CI instead of quietly reopening the wall.

Tests go in the matching `tests/` domain folder with unique basenames; rerun
`scripts/gen_test_index.py`.

---

## F. Open questions

1. **Built-in defaults vs. "no per-role default by design".** `get_board_scope` was written so
   that passing a role can never change what an existing run reads. C2 changes that for
   `reviewer`/`tester`. `warn` mode softens it; is a default-on wall the right call, or should
   defaults ship as a preset the user opts into?
2. **`team` executor.** Under `spawn-rules`, an orchestrator spawns builder/reviewer sub-agents
   directly and can pass the builder's output in the sub-agent prompt, bypassing the board
   entirely. Out of scope here; worth a note in the `spawn-rules` fragment.
3. **The working tree.** A reviewer still reads the builder's files and commit messages. The wall
   covers the board only; the diff is meant to be visible, the commit message arguably not.
4. **Process isolation.** C0 leaves direct DB and `BOARD.json` reads open. Closing them means
   running agents without read access to `~/.pathly/` and the board exports. Is that worth
   pursuing, or is "default paths are walled, bypass is visible" enough?
5. **Project-qualified feature boards.** Feature boards are keyed by feature name alone in a
   global DB, so same-named features in two projects share a board. Fixing that (a
   `project_root` on board identity) would also let C6 narrow the structural-lookup exception to
   the caller's project. It is a schema change, so it belongs in its own spec.
