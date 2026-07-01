---
name: User Stories
---
# Skill Fragment Composition — User Stories

## Context

Today a runner-mode stage prompt is assembled by `build_prompt()` (fsm_ops.py) as
`agent_map[state]` skill markdown + a small `## Current task` block. Each stage skill
(`team/build`, `team/review`, `team/test`, …) is a **monolith**: the logging contract,
feedback protocol, scout choreography, and sub-agent spawning rules are duplicated
prose inside every skill, so they drift.

This feature introduces a **declarative, YAML-driven composition layer**: small reusable
fragment skills + a central `composition.yaml` manifest that maps each stage skill to the
fragments it includes, with per-fragment **adapter gating** (`requires: can_spawn`). One
resolver assembles the final skill for both delivery modes (runtime `build_prompt` and
build-time `pathly-setup`).

**Division of labour stays fixed:** Python + FSM own the *macro* flow (which state, which
adapter, transitions, gates, caps). Fragments only describe *within-stage* behaviour. No
FSM-transition logic ever moves into a fragment.

This is **Track 1**. Track 2 (live event logging via a `progress-logging` fragment +
`POST /runner/log` → SSE) and Track 3 (a Studio Flow Wizard that composes flows visually)
are out of scope here and listed below as future work — Track 1 is their prerequisite.

---

## Stories

### Story S1: Fragment library + composition manifest
**As a** Pathly maintainer, **I want** a folder of small reusable fragment skills plus one
declarative manifest that says which fragments each stage skill composes, **so that** shared
behaviour (logging, feedback, scout, reporting, spawning) lives in exactly one place and
flows are assembled from data, not copied prose.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/skills/fragments/` contains: `progress-logging.md` (placeholder body for Track 2), `feedback-protocol.md`, `scout-choreography.md`, `completion-report.md`, `spawn-rules.md` — each lifted verbatim from the duplicated prose currently in `team/*.md`.
- [ ] `src/pathly_data/core/skills/composition.yaml` defines `version`, `fragments_dir`, a `defaults:` list (applied **only** to skills present in the `skills:` map), and a `skills:` map of `<skill> → fragments[]`. The `skills:` map starts **empty** in Conv 1 — stage entries are added in Conv 3 atomically with body reduction (see S3) to avoid a duplication window.
- [ ] A fragment entry may be a bare string (`feedback-protocol`) or an object with a gate (`{ name: spawn-rules, requires: can_spawn }`).
- [ ] The manifest is keyed by **skill name** (e.g. `team/build`), not by flow-state, so a skill reused across flows composes identically.
- [ ] Ordering is explicit and documented: assembled prompt = `[stage-specific skill body]` then `[defaults + skill fragments, in declared order]`.

**Edge Cases:** a skill **absent** from `skills:` is loaded **raw and unchanged** — no fragments, no defaults — preserving current behaviour until explicitly converted. An empty `fragments: []` for a *listed* skill means defaults only.

**Delivered by:** Conversation 1

---

### Story S2: Composition resolver + validator + adapter gating
**As a** Pathly maintainer, **I want** one `compose_skill(skill, adapter_caps)` resolver and a
manifest validator, **so that** both the runtime prompt builder and the build-time installer
produce identical, correctly-gated skills and a bad manifest fails loudly.

**Acceptance Criteria:**
- [ ] `compose_skill(skill, adapter_caps)` returns the assembled markdown: stage body + each resolved fragment, dropping any fragment whose `requires:` capability is false for the given adapter.
- [ ] `adapter_caps` is derived from the existing adapter `_meta` capability flags (e.g. `can_spawn`); claude keeps `spawn-rules`, an adapter with `can_spawn=false` drops it — with no per-adapter duplication of fragment text.
- [ ] A validator (in the spirit of `state.py`'s flow validation) rejects: unknown fragment name, unknown skill name, duplicate include, unknown `requires:` capability — raising a clear error, not silently dropping content.
- [ ] `build_prompt()` calls `compose_skill` at runtime using the live stage adapter.
- [ ] `pathly-setup` calls the same `compose_skill` at build time to materialise the static `~/.claude/skills/pathly-*.md` files.
- [ ] For the `claude` adapter, the composed output matches a **reviewed golden snapshot** and every shared section (logging, feedback, scout, completion, spawn) appears **exactly once** — no duplication, no dropped section — guarded by a snapshot test. (failure-case criterion)

**Edge Cases:** unknown adapter passed to `compose_skill` → clear error. A fragment file referenced by the manifest but missing on disk → validator fails the build.

**Delivered by:** Conversation 2

---

### Story S3: Convert build → review → test + anti-drift across adapters
**As a** Pathly maintainer, **I want** the three feedback-loop-heavy stage skills converted to
the composed form and the three adapters kept in sync, **so that** the architecture is proven
on the highest-payoff skills without a risky big-bang of all seven.

**Acceptance Criteria:**
- [ ] Both skill families — `team/{build,review,test}.md` (runner) **and** `development/{build,review,test}.md` (interactive, the ones `pathly-setup` actually installs) — are reduced to their distinct bodies; their shared middle now comes from fragments via the manifest. The two families keep different bodies (FSM-driven vs human-driven) but share fragments.
- [ ] `pathly-setup claude --apply` + `python -m build` regenerate all three adapters (claude/codex/copilot) from the composed core with no manual `_meta` edits. (anti-drift)
- [ ] A test fails if a committed adapter skill is stale relative to the composed core output. (failure-case criterion)
- [ ] `python -m pytest tests/ -q` is green; the existing runner/FSM tests still pass unchanged.
- [ ] `design`/`plan`/`storm`/`retro` are intentionally **not** converted here — noted as follow-up.

**Edge Cases:** codex/copilot lacking `can_spawn` produce composed skills with `spawn-rules` omitted and a flat fallback line instead.

**Delivered by:** Conversation 3

---

## Out of scope (future work)
- **Track 2 — Live event logging.** Flesh out `progress-logging.md` to instruct the agent to `POST /runner/log`; add the endpoint; supervisor re-broadcasts an `AGENT_PROGRESS` SSE; Monitor renders it. Track 1 ships the empty fragment as the seam.
- **Track 3 — Flow Wizard.** A Studio UI that lets a user assemble a new `<flow>.flow.yaml` + composition entries by picking states, per-stage skills, fragments, and adapters. Depends on Track 1's fragments + validator (the validator becomes the wizard's safety net).
- Converting `design`/`plan`/`storm`/`retro` to composed form.
