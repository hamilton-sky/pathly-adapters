# storage-restructure — feature-centric layout, scope-mirrored

Single canonical location per feature; storage mirrors the board scope hierarchy.

## Target tree

```
~/.pathly/                         GLOBAL scope (cross-project): pathly.db, lessons/
<project>/pathly/
  features/<name>/                 FEATURE scope
    plans/                         team pipeline (STATE.json, *.md, EVENTS, feedback/)
    goals/<slug>/  debugs/<slug>/  explorations/<slug>/  fixes/<slug>/
  project/                         PROJECT scope (cross-feature): goals/<slug>/, explorations/<slug>/,
                                   board-artifacts/, lessons/
  pipeline-walkthrough/            static docs
  .archive/<name>/                 completed features (mirrors features/ shape)
```

Board tier ↔ storage: feature→`pathly/features/<name>/`, project→`pathly/project/`,
global→`~/.pathly/`. Board **messages** already live scope-tagged in the DB; only artifact
**files** move. `project` is a SINGLE tier (board enum = feature|project|global) — one
project board, so `pathly/project/` is singular (no `project-<slug>`; if named project
boards are ever added, nest as `pathly/project/<slug>/`).

**T3 — global-tier goal home (deferred by design).** For goal DECOMPOSITION, `_goal_topic`
routes BOTH project- and global-tier goals to `pathly/project/goals/<slug>`; the `~/.pathly/`
global goal home is not stood up. This collapse is deferred by design — global goals are rare
(project goals normally become features rather than DAG-decomposed), and the collapse is
harmless (a global goal's plan/artifacts simply live under the project home). Stand up a
`~/.pathly/` goal home only if a concrete need appears. Resolves storage-restructure-p2 board
task 136db628 (see note 278dad33).

## Why this is safe to do now
Part 2 made every skill write to the resolved `<feature_path>` var, so agents are already
layout-agnostic — only `_resolve_storage_path`, the flow templates, and discovery change.

## Phases
1. **team pipeline → `pathly/features/<name>/plans/`** — team.flow template + resolver probe
   + reserved-name guard + CLI discovery (topic = feature dir, not "plans"). Legacy probe
   kept so existing features + ~15 tests stay green. ← THIS PHASE
2. **feature+scope addressing** — thread (feature, scope, slug) so goals/debugs/explorations/
   fixes nest under their feature; stand up `pathly/project/` + `~/.pathly/` homes; consultation
   + team-build (goal executors) → `features/<name>/goals/<slug>/`.
3. **Studio TS discovery + migrate existing folders + delete legacy probe** → true no-fallback.

## Reserved feature names (can't collide with pathly/ structural dirs)
features, project, plans, debugs, explorations, fixes, goals, lessons, board-artifacts,
pipeline-walkthrough, .archive
