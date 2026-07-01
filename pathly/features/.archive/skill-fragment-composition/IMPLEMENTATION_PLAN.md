---
name: Implementation Plan
---
# Skill Fragment Composition — Implementation Plan

## Goal
Replace monolithic stage skills with **YAML-declared composition** of small fragment skills,
gated per adapter. One resolver serves runtime (`build_prompt`) and build-time (`pathly-setup`).
Macro-flow ownership (FSM transitions, caps, adapter routing) is untouched.

## Architecture decisions (locked in discussion)
1. **Declarative central manifest** `core/skills/composition.yaml`, keyed by skill name — not flow-state, not skill frontmatter. Mirrors the existing `_meta/*.yaml` precedent.
2. **Adapter gating via `requires:`** computed from existing `_meta` capability flags (`can_spawn`). No fragment text duplicated per adapter.
3. **One resolver, two callers:** `compose_skill(skill, adapter_caps)` used by `build_prompt()` (runtime, live adapter) and `pathly-setup` (build-time, static files).
4. **Ordering:** `[stage body] + [defaults + skill fragments in declared order]`.
5. **Fragments never contain FSM-transition logic** — within-stage behaviour only.
6. **Phased rollout:** convert `build → review → test` only; leave the four light skills as follow-up.

## Component map
| Layer | File | Change |
|---|---|---|
| Data | `core/skills/fragments/*.md` | NEW — 5 fragments lifted from `team/*.md` |
| Data | `core/skills/composition.yaml` | NEW — manifest (`defaults`, `skills`, `requires`) |
| Orchestrator | `core/skills/compose.py` (or `fsm_ops` helper) | NEW — `compose_skill(skill, adapter_caps)` |
| Orchestrator | `state.py` (or new `compose_validate`) | NEW — manifest validator |
| Orchestrator | `fsm_ops.build_prompt()` | EDIT — call `compose_skill` instead of raw `_load_agent_text` |
| Install | `pathly-setup` build step | EDIT — materialise composed skills via `compose_skill` |
| Data | `core/skills/team/{build,review,test}.md` | EDIT — reduce to stage body |
| Tests | `tests/` | NEW — validator, resolver, claude round-trip, adapter staleness |

## Conversations (lite rigor)

### Conversation 1 — Fragment library + manifest (Story S1)
- Create `core/skills/fragments/` with `progress-logging.md` (stub body for Track 2), `feedback-protocol.md`, `scout-choreography.md`, `completion-report.md`, `spawn-rules.md`. Lift text verbatim from current `team/build.md`/`team/review.md`/`team/test.md`.
- Write `core/skills/composition.yaml` (`version`, `fragments_dir`, `defaults`, `skills`). **`skills:` starts empty** — no stage skill is converted yet, so no skill body is reduced. This keeps the fragments as inert data with zero behaviour change (no duplication window).
- **Verify:** `composition.yaml` parses; every referenced fragment file exists; manual diff shows fragment text matches what was lifted.

### Conversation 2 — Resolver + validator + wiring (Story S2)
- Implement `compose_skill(skill, adapter_caps)` (drop `requires:`-gated fragments when capability false). A skill **absent** from `skills:` returns its raw body unchanged — so with the empty manifest from Conv 1, this is a pure no-op at runtime.
- Implement manifest validator (unknown fragment/skill, dupes, unknown capability → raise).
- Wire `build_prompt()` to `compose_skill` (runtime, live adapter).
- Wire `pathly-setup` to `compose_skill` (build-time materialisation).
- **Verify:** `pytest tests/ -q`; resolver/validator unit tests pass; because `skills:` is still empty, every existing skill is byte-identical to before — confirming the seam is inert before any conversion.

### Conversation 3 — Convert build/review/test + anti-drift (Story S3)
- **Atomic per skill:** in one step, add the `team/{build,review,test}` entries to `composition.yaml` *and* reduce each `team/*.md` to its stage body. Never leave a skill declared-but-not-reduced (would duplicate sections) or reduced-but-not-declared (would drop sections).
- Add the **golden snapshot test** for claude: composed `team/build|review|test` matches a reviewed snapshot, every shared section appears exactly once.
- Run `pathly-setup claude --apply` + `python -m build`; regenerate all three adapters.
- Add staleness test (committed adapter skill must equal composed core output).
- **Verify:** `pytest tests/ -q` green; adapters regenerate clean; no manual `_meta` edits.

## Dependency
Strict `1 → 2 → 3`. Conv 2 depends on the manifest from Conv 1; Conv 3 depends on the resolver from Conv 2.

## Risks / guards
- **Behaviour drift for claude** → round-trip snapshot test (S2) is the gate before converting skills (S3).
- **3-adapter sync rule** (pathly_data/CLAUDE.md) → Conv 3 uses the official build step only; staleness test enforces it.
- **Macro/micro boundary** → reviewer must reject any fragment that contains FSM-transition/next-state logic.

## Architecture finding — development vs team split (Conv 2)

There are **two** build/review/test skill families, and they are not duplicates:

- `core/skills/development/{build,review,test}.md` — the **interactive** `/pathly build` command.
  Installed by `pathly-setup` as `~/.claude/skills/pathly-*/SKILL.md` (via `_SKILL_GROUPS["build"]="development"`).
  The **human** drives the loop: git pre-flight prompt, scope confirmation, self-chaining in fast mode.
- `core/skills/team/{build,review,test}.md` — the **runner** orchestration skill. NOT installed;
  assembled only at runtime by `build_prompt()` (`agent_map["BUILDING"]="team/build"`). The **Python
  FSM/supervisor** drives the loop: no human prompts, full feedback ladder + guards, returns to orchestrator.

They share a *middle* (analyze→scout→implement, `<usage>`+log-agent-done, builder/scout spawning) which
is today copy-pasted — that is the duplication this feature removes. Decision (locked): the manifest
covers **both families**, sharing fragments, each keeping its distinct body. This also makes both
resolver callers real — runtime `build_prompt` composes `team/*`; build-time `pathly-setup`/`stitch_skill`
composes the installed `development/*`, so the S3 adapter-staleness test has something to bite on.

**Manifest key convention:** core-skills-relative path without `.md` — `team/build`, `development/build`.
At build time this is derived as `f"{_SKILL_GROUPS[skill]}/{skill}"`.

## Out of scope
Track 2 (live logging), Track 3 (flow wizard), and converting design/plan/storm/retro. See USER_STORIES "Out of scope".
