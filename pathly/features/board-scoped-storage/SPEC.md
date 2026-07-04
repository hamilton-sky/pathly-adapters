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
2. **Existing shared-bucket folders + stale DB refs** → **migrate into their boards** (dry-run
   first; infer the board from the DB message scope, fall back to `project/`).

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

### 4. Migration (P2)
For each entry under `pathly/{debugs,explorations,fixes}/<x>/`: look up its board+scope in the DB
(`comms_messages` where the run posted), move the folder to `<board-dir>/<kind>/<x>/` (or
`project/<kind>/<x>/` if board-less), and repath the DB refs (`comms_artifacts.path`,
`comms_messages.artifact_path`, `context_refs`) to the new location — **dry-run first**, only where
the file actually moves. (Subsumes retrieval-robustness S2.)

## Phases

- **P1 — new runs nest.** `board_run_topic` + 3 flow templates + launch threading + a
  layout-invariant test (a debug/explore/fix run on a feature board resolves under
  `features/<f>/<kind>/<slug>`; board-less resolves under `project/<kind>/<slug>`). No data move.
- **P2 — migrate existing.** Move the ~5 shared-bucket folders under their boards + repath the DB
  refs (dry-run first). Retire retrieval-robustness S2 into this.
- **P3 — retire the buckets.** Drop `debugs`/`explorations`/`fixes` from the shared-bucket discovery
  paths, add the nested kinds to Studio's `KNOWN_PATHLY_DIRS`, update docs. Keep the names in the
  reserved-name set (they are still structural sub-dirs, now under a board).

## Invariants / load-bearing (do not break)

- Reserved-name set (`storage_paths.py`) keeps `debugs`/`explorations`/`fixes`/`goals` — they are
  still structural dir names, now one level deeper.
- `cli/_discovery.py` + hydration allowlist must resolve the nested `<kind>/<slug>` paths.
- The team pipeline's flat feature files (STATE.json/EVENTS.jsonl) are unchanged.
- Reads AND writes must land in the same place after each change — extend the layout-invariant test.
