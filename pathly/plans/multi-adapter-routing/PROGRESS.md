---
name: Progress
---
# Multi-Adapter Routing — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | FSM emits preferred_adapter | Conv 1 | DONE |
| S2 | Flow validator accepts/checks adapter_map | Conv 2 | DONE |
| S3 | Studio wizard authors adapter routing | Conv 3 | TODO |
| S4 | pathly-dispatch coordinator routes the stage | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 0-2 | S1 | DONE | `python -m pytest tests/ -q` |
| 2 | 3-6 | S2 | DONE | `python -m pytest tests/ -q` |
| 3 | 7-9 | S3 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` + launch Studio |
| 4 | 10-11 | S4 | TODO | `pathly-setup claude --apply` succeeds; `~/.claude/skills/pathly-dispatch/SKILL.md` exists |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

**Dependency:** 1 → 2 → 3 (critical path); 4 needs only 1. Conv 2 and Conv 4 can run in parallel after Conv 1.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 0 Pre-flight | none | Baseline tests + confirm anchors | Baseline green, anchors confirmed | DONE |
| 1 | 1 FSM resolve+emit | `src/pathly_orchestrator/fsm_ops.py` | `_resolve_adapter` + `preferred_adapter` in both responses | `/next_action` returns the field | DONE |
| 1 | 2 Unit tests | `tests/` | present/absent/default-only/unmatched | Cases pass | DONE |
| 2 | 3 Known set + key | `src/pathly_orchestrator/state.py` | `_KNOWN_ADAPTERS` + optional key | `adapter_map` accepted | DONE |
| 2 | 4 Validate shape | `src/pathly_orchestrator/state.py` | default-required, closed-set, state-key checks | Bad maps fail clearly | DONE |
| 2 | 5 Doc + example | `src/pathly_data/CLAUDE.md`, `core/flows/team.flow.yaml` | Canonical shape doc + example block | Both updated | DONE |
| 2 | 6 Round-trip test | `tests/` | Fixture passes; bad value fails | Tests pass | DONE |
| 3 | 7 generateYaml | `studio/.../FlowWizard/utils.ts` | Emit `adapter_map` block | Block emitted only when non-trivial | TODO |
| 3 | 8 Wizard step | `studio/.../FlowWizard/Step5AdapterRouting/` | New component + CSS | Step renders, tokens only | TODO |
| 3 | 9 Wire step | `studio/.../FlowWizard/FlowWizard.tsx`, `draftUtils.ts`, `types.ts` | State, render, TOTAL_STEPS=6, draft | Step reachable, draft restores | TODO |
| 4 | 10 Dispatch skill | `src/pathly_data/core/skills/utilities/dispatch.md` | Deterministic relay/handoff | Decision logic present | TODO |
| 4 | 11 Skill meta ×3 | `adapters/{claude,codex,copilot}/_meta/dispatch_skill.yaml` | Install meta for 3 adapters | `pathly-setup` installs skill | TODO |

## Prerequisites
- FSM reachable on `127.0.0.1:8765`.
- Studio node deps installed.

## Blocked By
- Nothing
