# composition-blocks — Progress

## Status: Conv 1 DONE

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | Default block library in composition.yaml | Conv 1 | DONE |
| S2 | Block resolver in compose.py | Conv 1 | DONE |
| S3 | Block validation in validate_composition | Conv 1 | DONE |
| S4 | flow yaml `composition:` key validation | Conv 2 | TODO |
| S5 | Runtime block injection in build_prompt | Conv 2 | TODO |
| S6 | Studio block authoring form | Conv 3 | TODO |
| S7 | Studio wizard per-stage block dropdown | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 0 | Pre-flight | — | DONE | `python -m pytest tests/ -q` (record baseline) |
| 1 | 1, 2, 3 | S1, S2, S3 | DONE | `python -m pytest tests/test_compose.py -q` |
| 2 | 4, 5 | S4, S5 | TODO | `python -m pytest tests/ -q` |
| 3 | 6, 7 | S6, S7 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 0 | Pre-flight | (read-only) | Record baseline test counts + typecheck result; glob-verify all touchpoint paths | Baseline recorded in feedback/PREFLIGHT.md | DONE |
| 1 | Phase 1 | `src/pathly_data/core/skills/composition.yaml` | Add `blocks:` map with 3 default blocks | File has `blocks:` key; `validate_composition()` clean | DONE |
| 1 | Phase 2 | `src/pathly_orchestrator/compose.py` | Add `resolve_block` + `compose_skill_with_block` | Valid call returns string; unknown block raises | DONE |
| 1 | Phase 3 | `src/pathly_orchestrator/compose.py` + `tests/test_compose.py` | Extend `validate_composition` for blocks; add block unit tests | All new tests pass; existing tests unaffected | DONE |
| 2 | Phase 4 | `src/pathly_orchestrator/state.py` + flow validator tests | Register `composition:` in allowed keys; validate state keys + block names | Valid flow passes; undeclared state + unknown block fail | TODO |
| 2 | Phase 5 | `src/pathly_orchestrator/fsm_ops.py` | Wire `build_prompt` to resolve stage block when flow declares one | Bound state uses block fragments; unbound state uses default | TODO |
| 3 | Phase 6 | `studio/.../FlowWizard/BlockAuthorForm/` (NEW) | Block authoring form component | Renders 5 fragments; validates; writes user-blocks.json | TODO |
| 3 | Phase 7 | `studio/.../FlowWizard/Step4Agents/`, `FlowWizard.tsx`, `types.ts`, `utils/generateYaml` | Per-stage dropdown + yaml emission | Wizard emits `composition:` map; typecheck clean | TODO |

## Prerequisites

- Python test suite runnable (`python -m pytest tests/ -q`)
- Studio typecheck runnable from repo root (`node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`)
- All 5 fragment files exist under `src/pathly_data/core/skills/fragments/`

## Blocked By

- Nothing
