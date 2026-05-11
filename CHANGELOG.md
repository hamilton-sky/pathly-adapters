# Changelog

## 2.0.0 — 2026-05-12

### Breaking changes

- **All skills now install as `pathly-*`** — installed slash commands are `/pathly-build`,
  `/pathly-retro`, `/pathly-explore` etc. instead of `/build`, `/retro`, `/explore`.
  If you had direct skill invocations bookmarked, update them to use `/pathly <subcommand>`.
- **`/pathly` is the single user-facing entry point.** Direct slash commands like `/build`,
  `/help`, `/start`, `/end` no longer exist after reinstall with this version.
- **Feature argument removed from invocations.** Commands that previously required a feature
  name (`/pathly retro my-feature`, `/pathly team-flow my-feature`) now auto-detect the
  active feature from `plans/*/STATE.json`. Pass a feature name only when you need to
  override auto-detection.

### New skills

- **`/pathly explore`** — codebase investigation via the new `explorer` agent (analyze →
  scout-flow → trace → conclude). Replaces the previous direct scout spawn.
- **`/pathly test`** — standalone acceptance test runner (tester + scout-flow pipeline).
  Previously only available inside `team-flow`.

### New agents

- **`explorer`** — three-phase agent (analyze / explore / conclude) that orchestrates
  scout-flow for codebase investigations. Spawned by `/pathly explore`.

### Improvements

- **Dispatcher now covers all subcommands.** `/pathly retro`, `/pathly archive`,
  `/pathly lessons`, `/pathly prd-import`, `/pathly team-flow`, `/pathly plan`,
  `/pathly review`, `/pathly test` are all properly routed. Previously these hit the
  catch-all and were misrouted through the director.
- **`build` and `storm` route directly** to their skills instead of going through the
  director first.
- **scout-flow integrated** into `explore`, `test`, and `team-flow/test` — all three now
  use the standard analyze → scout-flow → implement/test phases matching builder and reviewer.
- **Discovery path 4** in `team-flow` now routes through the `explore` skill (explorer +
  scout-flow) instead of spawning a scout inline.
- **`tester` agent** updated to use `phase: analyze` / `phase: test` protocol, matching
  the builder/reviewer/planner/architect pattern.
- **`help` menu** updated: `/pathly explore` and `/pathly test` added to all states;
  no-feature menu now offers explore as option 4.

### Migration

Run `pathly-setup --repair` after upgrading to reinstall skills with the new `pathly-*`
naming. Old skill directories (`build/`, `explore/`, etc.) will be replaced with the new
prefixed names (`pathly-build/`, `pathly-explore/`, etc.).

---

## 1.1.0 — 2026-05-11

- Add missing skill YAMLs for go, start, end, pause, help, meet across all adapters
- Add full skill set to codex and copilot adapters
- Sync README, flow diagram, and architecture with current skill set and install flow
- Document Windows broken-stub issue when pip-installing outside pipx
