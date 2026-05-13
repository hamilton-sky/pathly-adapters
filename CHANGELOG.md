# Changelog

## 2.1.0 — 2026-05-13

### Orchestrator and hooks are now first-class shipped packages

- Move `orchestrator/` → `src/pathly_orchestrator/` and `hooks/` → `src/pathly_hooks/`
  so both ship in the installed wheel. The repo-root copies are removed.
- Add `pathly-events summary <feature>` console script — prints a token/cost table
  from `plans/<feature>/EVENTS.jsonl`.
- Add `pathly-state <feature>` console script — prints current FSM state from
  `plans/<feature>/STATE.json`.
- This is non-breaking for end users: the repo-root `orchestrator/` and `hooks/`
  directories were never exported by prior releases.

### FSM hardening

- `schemas/state.schema.json` — JSON Schema with all 13 state names and allowed-transitions
  table. `write_state` and `append_event` validate against it at write time; invalid state or
  illegal transition raises `ValueError`.
- `eventlog.append_event` is now concurrency-safe via `fcntl.flock` / `msvcrt.locking`.
- `state.schema.json` gains an optional `iteration_by_stage` map (key = FSM stage name,
  value = attempt count) alongside the existing `retry_count_by_key`.

### Hook contract integrity

- `classify_feedback.py` — drop `"how"` keyword trigger; use word-boundary regex for all
  keywords; keyword set extended with `layer`, `boundary`.
- `protocol_contract.yaml` gains `version: 1`; `pathly_hooks.PROTOCOL_VERSION` constant
  cross-checked at import. Desync raises loudly.

### Hook deployment to Codex and Copilot VS Code

- `pathly-setup codex --apply` writes `~/.codex/hooks.json` with two `PostToolUse` entries
  under a `"pathly"` namespace key. Merge-safe: user hooks outside the `"pathly"` key are
  never touched. `--uninstall` removes only the `"pathly"` key.
- `pathly-setup copilot --apply` writes `.github/hooks/pathly-classify.json` and
  `.github/hooks/pathly-ttl.json` with platform-keyed commands (windows/linux/osx).
  `--uninstall` deletes both files.
- Codex `install.yaml` hook event updated from `post_tool_call` → `PostToolUse`; matcher
  added (`tool_name: apply_patch`).
- `docs/SECURITY.md` — new "Hook surface coverage" table documenting per-host deployment
  status; README links to it under Known Limitations.

### Skill system refactor (breaking rename)

- `scout-flow` renamed to **`scout-path`** across all adapters (claude, codex, copilot).
  `scout-path` is now properly installed via `scout-path_skill.yaml` — it was previously
  missing from all adapter manifests.
- `team-flow` renamed to **`team`** across all adapters and all skill content files.
  `/pathly team-flow` → `/pathly team`. Sub-skills follow: `team/build`, `team/discover`, etc.
- Build skill (`/pathly build`) no longer owns mode selection, commits, or PROGRESS.md
  updates. Those are the orchestrator's (`/pathly team`) responsibility.
- `/pathly team` now asks auto/manual mode once at entry, commits after BUILDING→REVIEWING,
  and marks PROGRESS.md DONE only after REVIEWING→TESTING (reviewer passed).

---

## 2.0.3 - 2026-05-12

- Fix Codex plugin installation by creating a real local marketplace copy and enabling `pathly@pathly-local` in Codex config.
- Use relative `./skills/` and `./agents/` paths in the Codex plugin manifest.
- Add regression coverage for Codex marketplace install, idempotency, and uninstall.

---

## 2.0.2 — 2026-05-12

- Add the PO phase to `team-flow/plan` so `PO_NOTES.md` is created before planner decomposition.
- Separate PO requirements authorship from planner decomposition and add `ARCH_QUESTION` escalation rules for planner and tester.
- Install a complete Codex plugin bundle under `~/.codex/plugins/pathly`, including plugin-local agents and skills, so Pathly can appear as a Codex plugin.
- Accept Codex skill metadata that uses `natural_language` instead of slash-command `invocation`.

---

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
