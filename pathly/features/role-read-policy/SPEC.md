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
- Restricting the human / Studio UI: un-attributed UI reads stay unrestricted.

---

## C. Design

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
  `from_agent ∈ exclude_authors`). Both lists together mean "this kind of post *from these
  roles*", which is the precise wall we want (a reviewer still sees a `discovery` from the
  explorer or the architect).
- **Never withheld, whatever the policy:** governance (pending decisions, active escalations),
  `decision`, `constraint`, `goal`/`task` rows, and the run's own posts. Governance is injected
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
| everyone else | — | — | unchanged |

`warning` is withheld from the reviewer only when authored by the builder: a builder warning
("this path is untested") is exactly the hint that steers a reviewer away from a real defect.
Up for debate in review of this spec.

### C3. One policy function, three read paths

A single pure function, e.g. `runner/read_policy.py::apply_read_policy(rows, policy, run)`,
used by:

1. `retrieve_board_context` — after `_is_context`, before budgeting, on both the semantic and the
   recency-fallback rows.
2. `POST /comms/search` — after the search, before returning.
3. `GET /comms` — same.

Keeping it one function is the point: the assessment's through-line is "trusted, not enforced",
and three hand-copied filters drift.

### C4. Who is asking — run identity on pull paths

The pull routes cannot apply a role policy without knowing the caller's role.

- Add optional `run_id` to the `/comms/search` body and `GET /comms` query, and update the
  `board-search` (and `board-init`) fragment to pass `<run_id>`, the same variable `comms-post`
  already passes when posting (`messages_write.py:131`).
- The server resolves `run_id → (role, feature, project_root, board, scope)` from a **spawn-time
  record**, never from the request body. A body-supplied `role` is ignored for policy purposes —
  otherwise a reviewer could ask as `human`.
- **Open item:** `agent_invocations.agent_role` (`db/migrations.py:77`) is a projection of
  `AGENT_DONE`, so it is written *after* the run, too late for mid-run reads. The build must find
  or add a record written at spawn (the supervisor knows role + scope when it composes the prompt;
  `supervisor/task_prompt.py`, `supervisor/board_run.py:342`).
- A request **without** `run_id` is treated as the UI/human and stays unrestricted.

### C5. Enforcement modes (rollout safety)

`read_policy.mode` setting: `off` | `warn` | `enforce`. Default `warn`.

- `warn`: compute the policy, return everything, and log + count what *would* have been
  withheld (and any cross-pair read, C6). Ships first, so real runs show the impact before
  anything is hidden.
- `enforce`: withhold.
- The "no `run_id` = unrestricted" loophole is closed only by `enforce` + a per-run token
  (C4 follow-up). In `warn` it is just measured: how many agent calls arrive without a `run_id`.

### C6. `(board, scope)` pair binding (ISSUE-1, read side)

- With a resolved run, a pull request may only target the pairs the run is entitled to:
  `search_tiers_value` (`runner/board_scope.py:47`) already renders exactly that set. A request
  for another pair (e.g. another feature's board) is refused in `enforce` (empty result + an
  explicit `reason`, not a silent `[]` that "reads like the board knows nothing") and counted in
  `warn`.
- Add a query helper that **requires** both `board` and `scope` and use it in the comms read
  queries, as ASSESSMENT ISSUE-1 proposes.

### C7. Visibility

- `record_board_context` / `render_stats` (`runner/context_record.py`) gain a `withheld` count
  per reason (`type`, `author`, `pair`).
- The context preview (`POST /comms/agent-context/preview`, `blueprints/comms/context.py`) already takes
  `role`; it shows withheld rows greyed with the rule that hid them, so a human can see the wall.

---

## D. Phases (each → one board task)

| # | Phase | Priority | Risk | Done when |
|---|---|---|---|---|
| P1 | Policy shape + `apply_read_policy` + built-in defaults, pure and unit-tested | P0 | Low | function tests cover every rule in C1/C2, incl. governance never withheld |
| P2 | Wire into the push path (`retrieve_board_context`, semantic + recency) in `warn` | P0 | Low | context record shows withheld counts; prompt unchanged in `warn` |
| P3 | Spawn-time run record + `run_id` on `/comms/search` and `GET /comms`; fragments pass it | P0 | Med | a search with a reviewer `run_id` returns the policy-filtered set; body `role` ignored |
| P4 | `(board, scope)` pair binding on pull routes + required-pair query helper | P1 | Med | cross-feature pull refused in `enforce` with a reason; invariant test over all comms reads |
| P5 | Preview + Studio visibility of withheld rows | P1 | Low | preview for `role=reviewer` shows what is hidden and why |
| P6 | Flip default to `enforce` after a `warn` soak on real runs | P1 | Med | soak data reviewed; no review stage starved of needed context |

P1–P3 are the minimum that makes "independent reviewer" true. P4 closes the cross-feature leak.

---

## E. Tests

- Unit (`apply_read_policy`): type-only, author-only, type∧author, empty lists, governance and
  `decision`/`constraint` always kept, own-run posts kept, unknown role → no filter.
- Resolution: per-role row beats built-in default; explicit row with no `exclude_*` keys reads
  as today (back-compat).
- Push path: reviewer context for a board seeded with builder `discovery` + architect `discovery`
  + a pending decision → only the latter two appear (in `enforce`); all three in `warn` with a
  withheld count of 1.
- Pull path: same seed via `/comms/search` with a reviewer `run_id`; body `role: "human"` does
  not lift the filter; no `run_id` → unrestricted.
- Pair binding: a feature-A run searching `board=feature, scope=B` → refused with a reason in
  `enforce`; counted in `warn`.
- Recency fallback (no embedding) filtered the same as the semantic path.

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
4. **Per-run token.** Is a spawn-issued token (C5) worth it for a local, single-user engine, or is
   `run_id` + `warn` metrics enough until Pathly is multi-user?
