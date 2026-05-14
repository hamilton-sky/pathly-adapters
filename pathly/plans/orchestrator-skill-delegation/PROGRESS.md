# orchestrator-skill-delegation — Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | commit skill | Conv 1 | DONE |
| S2 | archive-artifacts skill | Conv 1 | DONE |
| S3 | orchestrator pure delegation | Conv 2 | TODO |
| S4 | debug + explore auto-commit | Conv 3 | TODO |
| S5 | fix debug FIXING agent bug | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1–4 | S1, S2 | DONE | `pytest src/` |
| 2 | 5–6 | S3 | TODO | diff orchestrator source vs installed |
| 3 | 7–10 | S4, S5 | TODO | diff all three flow YAMLs source vs installed |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1 | `src/pathly_data/core/skills/commit.md` | CREATE commit skill | file exists with guard + git commands + event append | DONE |
| 1 | 2 | `src/pathly_data/adapters/claude/_meta/commit_skill.yaml` | CREATE commit adapter meta | meta YAML installs to pathly-commit/SKILL.md | DONE |
| 1 | 3 | `src/pathly_data/core/skills/archive-artifacts.md` | CREATE archive-artifacts skill | file exists with copy logic + event append | DONE |
| 1 | 4 | `src/pathly_data/adapters/claude/_meta/archive-artifacts_skill.yaml` | CREATE archive-artifacts adapter meta | meta YAML installs to pathly-archive-artifacts/SKILL.md | DONE |
| 2 | 5 | `src/pathly_data/core/agents/orchestrator.md` | MODIFY Execute transition_actions | section is ≤10 lines, no shell commands | TODO |
| 2 | 6 | `C:/Users/Yafit/.claude/agents/orchestrator.md` | SYNC installed orchestrator | matches source Execute transition_actions section | TODO |
| 3 | 7 | `src/pathly_data/core/flows/team.flow.yaml` | MODIFY type: → skill: | no type: keys in transition_actions | TODO |
| 3 | 8 | `src/pathly_data/core/flows/debug.flow.yaml` | MODIFY FIXING bug + add transition_actions | FIXING: builder, transition_actions with skill: | TODO |
| 3 | 9 | `src/pathly_data/core/flows/explore.flow.yaml` | MODIFY add transition_actions | transition_actions with skill: | TODO |
| 3 | 10 | installed flow YAMLs ×3 | SYNC all three installed copies | all match source | TODO |

## Prerequisites
- Run `pytest` before Conv 1 and record pre-existing failures as baseline

## Blocked By
- Nothing
