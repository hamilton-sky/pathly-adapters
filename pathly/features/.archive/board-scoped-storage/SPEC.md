# board-scoped-storage — every run writes under its board

**Status:** SPEC · **Date:** 2026-07-05 · **Completes:** storage-restructure Phase 2

Goals already nest under their board (`_goal_topic`). This threads the *other* run kinds —
**debug, explore, quick-fix** — the same way, so a flow run **on a board** writes **under that
board's folder** instead of a shared top-level bucket. This is the unfinished half of
storage-restructure Phase 2 ("thread (feature, scope, slug) so goals/debugs/explorations/fixes
nest under their feature").

## Principle

**Board scope decides *where*; the flow decides *what kind* + the pipeline.**
- feature board → `pathly/features/<scope>/<kind>/<slug>/`
- project board → `pathly/project/<kind>/<slug>/`
- global board → `~/.pathly/<kind>/<slug>/`  (project/global collapse deferred per storage-restructure T3)

where `kind ∈ {goals, explorations, debugs, fixes}`.

## Decisions (2026-07-05)

1. **Board-less runs** (standalone `/pathly explore <x>` with no board context) default to the
   **PROJECT board** → `pathly/project/<kind>/<slug>/`. No new shared buckets.
2. **Existing shared-bucket folders** → **migrate into their boards** (dry-run first; infer the
   board from the DB message scope, fall back to `project/`). **Verified 2026-07-05: P2 is a pure
   folder move — 0 DB refs point at these folders** (the stale DB refs are all `pathly/plans/` =
   retrieval-robustness S2, a *separate* DB-only repath — see §4).

## Problem (current state)

Flow templates couple the flow to a fixed top-level location, ignoring the board:

| Flow | writes to | board-scoped? |
|---|---|---|
| `team`, `test` | `pathly/features/{topic}/` | ✅ |
| `consultation`, `team-build` | `pathly/{topic}/` (topic = scope-nested path) | ✅ via `_goal_topic` |
| `debug` | `pathly/debugs/{topic}/` | ❌ shared bucket |
| `explore` | `pathly/explorations/{topic}/` | ❌ shared bucket |
| `quick-fix` | `pathly/fixes/{topic}/` | ❌ shared bucket |

Concrete evidence of the leak: `pathly/explorations/production-readiness-plan/` AND
`pathly/features/production-readiness-plan/` both exist — an explore run on the production-readiness
board landed in the shared bucket, not under the board. No feature has a nested `goals/`/
`explorations/`/`debugs/` subdir on disk today.

`_goal_topic` also **hardcodes `goals/`** — even a debug flow run via the goal `team` executor lands
in `goals/<slug>`, not `debugs/<slug>`.

## Target tree

```
~/.pathly/                              GLOBAL board  (pathly.db, lessons/, <kind>/<slug>/, .archive/)
<project>/pathly/
  features/<name>/                      FEATURE board
    STATE.json EVENTS.jsonl PROGRESS.md feedback/    ← team pipeline (flat, unchanged)
    goals/<slug>/ explorations/<slug>/ debugs/<slug>/ fixes/<slug>/
    artifacts/
  features/.archive/<name>/             archived features
  project/                              PROJECT board
    goals/<slug>/ explorations/<slug>/ debugs/<slug>/ fixes/<slug>/
    board-artifacts/ lessons/ .archive/<slug>/
  pipeline-walkthrough/                 static docs (not a board)
```

Archive **mirrors the scope** (feature→`features/.archive/`, project→`project/.archive/`,
global→`~/.pathly/.archive/`); no separate global archive folder.

## Design

### 1. `board_run_topic(board, scope, kind, slug)` — generalize `_goal_topic`
```
feature + scope → f"features/{scope}/{kind}/{slug}"
otherwise       → f"project/{kind}/{slug}"          # project + global (T3 deferral)
```
Keep `_goal_topic(b,s,sl) = board_run_topic(b,s,'goals',sl)` as a thin back-compat wrapper.
Route through the ONE feature-dir resolver (`_resolve_storage_path`) — its `pathly/<topic>`
candidate lands the nested path, exactly as goals do today.

### 2. Flow templates → `pathly/{topic}/`
`debug`, `explore`, `quick-fix` templates change from `pathly/<kind>/{topic}/` to `pathly/{topic}/`
so the *topic* carries the nested path (identical to how `consultation`/`team-build` already work).
Flows load DB-first: re-seed the flow rows on server start (`_refresh_flows`), and migrate any stale
DB flow rows.

### 3. Launch threading
When a debug/explore/fix flow is launched **from a board**, build the topic via `board_run_topic`
(board+scope+kind+slug). Standalone `/pathly <kind>` with no board → **project** board
(`project/<kind>/<slug>`). The interactive skills that establish the run dir must resolve through
`<feature_path>` / the resolver, never a hardcoded `pathly/<kind>/` prefix.

### 4. Migration (P2) — dry-run findings (2026-07-05)

Inventory via [`p2_inventory.py`](./p2_inventory.py) (co-located; read-only against the real
`~/.pathly/pathly.db`; re-run before `--apply` since data may drift):

- **9 shared-bucket folders on disk**: 2 `debugs/`, 7 `explorations/`, 0 `fixes/`.
- **0 references in the COMMS-BOARD tables** — `comms_artifacts.path`, `comms_messages.artifact_path`,
  and `context_refs` all have **zero** hits (no board-hydration risk).
- **`fsm_state` was overlooked in the first pass (correction 2026-07-05).** 2 folders with a
  `STATE.json` (`codebase-architecture` = PLANNING, `unified-cli-composition` = DONE) have
  authoritative rows in the runtime FSM-state table. `STATE.json` is only a *mirror*; `fsm_state`
  (keyed by `(project_root, feature)`) is the source of truth. A naive move would orphan those rows
  because `eventlog` derived `project_root` by a depth-hardcoded "3 levels up" — see §5. So the move
  is safe **only after** the §5 foundation fix.
- Board-inference: **8 → `project/<kind>/<slug>/`** (nothing references them ⇒ agreed default);
  **1 → feature**: `explorations/production-readiness-plan/` slug-matches the
  `production-readiness-plan` feature ⇒ `features/production-readiness-plan/explorations/production-readiness-plan/`
  (doubled name — **confirm intent before moving**; otherwise send it to `project/` like the rest).

**Disentangled from S2 (correction).** The DB's stale refs are all `pathly/plans/…` — that is
retrieval-robustness **S2** / production-readiness **G2**, a **DB-only** repath handled by
[`../retrieval-robustness/s2_repath.py`](../retrieval-robustness/s2_repath.py), *separate* from
moving these folders. P2 does **not** subsume S2; they
are two independent migrations that merely share the "stale storage path" theme.

Move mechanics: with §5 landed, `git mv` each folder to its target (preserves history **and** the
correct `fsm_state` key, since the basename is unchanged); the 1 renamed slug has no `fsm_state` row.
Apply is a separate reviewed step.

### 5. Foundation: nesting-aware state keying (prerequisite — discovered mid-P2, FIXED 2026-07-05)

`eventlog` keys the authoritative `fsm_state` table (and the event log) by `(project_root, feature)`,
deriving `project_root = feature_dir.parent.parent.parent` — a **hardcoded "3 levels up"** that only
holds for the flat `pathly/<container>/<name>` depth. For a nested run it mis-derives:

| run dir | old (3-up) `project_root` | correct |
|---|---|---|
| `pathly/features/<n>` (flat) | `<root>` | ✅ |
| `pathly/project/<kind>/<n>` | `<root>/pathly` | ❌ |
| `pathly/features/<f>/<kind>/<n>` | `<root>/pathly/features` | ❌ |

This is a **split-brain**: the `STATE.json` mirror moves with the folder, but the DB lookup at the new
depth computes a different key and misses. P2 surfaced it (2 folders carry `fsm_state`), but it is
really a **latent P1 bug** — every *new* nested debug/explore/goal run would key its state under the
wrong root. (`fsm_state` already holds mis-derived rows: `project_root=C:/` and `.../studio`.)

**Fix:** `eventlog._project_root_of(feature_dir)` finds the ancestor directly above the `pathly/`
segment at any depth — byte-identical for flat/legacy paths, correct for nested. Guarded by
`test_eventlog_keys_nested_run_by_true_project_root`. Because it preserves the `feature` basename key,
existing rows are untouched and the P2 move needs **no re-keying**.

**Known follow-up (not fixed here):** the `feature` key is the basename only, so two nested runs with
the same slug under different boards collide on `(project_root, slug)`. Rare with descriptive slugs;
the durable fix keys by the board-relative path. Tracked, out of scope for this fix.

## Phases

- **P1 — new runs nest.** `board_run_topic` + 3 flow templates + launch threading + a
  layout-invariant test (a debug/explore/fix run on a feature board resolves under
  `features/<f>/<kind>/<slug>`; board-less resolves under `project/<kind>/<slug>`). No data move.
- **P2 — migrate existing.** Move the **9** shared-bucket folders under their boards (8 → `project/`,
  1 → feature). **Pure `git mv`; 0 DB refs to repath** (verified 2026-07-05, see §4). S2
  (`pathly/plans/` DB refs) is a *separate* DB-only migration, **not** folded in here.
- **P3 — retire the buckets.** Drop `debugs`/`explorations`/`fixes` from the shared-bucket discovery
  paths, add the nested kinds to Studio's `KNOWN_PATHLY_DIRS`, update docs. Keep the names in the
  reserved-name set (they are still structural sub-dirs, now under a board).

> **P2↔P3 ordering (verified 2026-07-05 — do P3's discovery changes WITH or BEFORE P2's move).**
> The move is clean for *data* (0 DB refs) but not yet for *visibility*: `project` is **not** in
> Studio's `KNOWN_PATHLY_DIRS` (`useProjectFiles.ts`), so `pathly/project/…` renders only as a generic
> "custom" section; and `cli/_discovery.py` walks `features/*/STATE.json` (+ legacy `plans/`) but
> **not** `features/*/<kind>/*`, so feature-nested runs aren't discovered until it learns the nested
> kinds. Shipping P2 alone would make moved folders hard to see in Studio. Treat P2+P3 as one unit.

## Invariants / load-bearing (do not break)

- Reserved-name set (`storage_paths.py`) keeps `debugs`/`explorations`/`fixes`/`goals` — they are
  still structural dir names, now one level deeper.
- `cli/_discovery.py` + hydration allowlist must resolve the nested `<kind>/<slug>` paths.
- The team pipeline's flat feature files (STATE.json/EVENTS.jsonl) are unchanged.
- Reads AND writes must land in the same place after each change — extend the layout-invariant test.
