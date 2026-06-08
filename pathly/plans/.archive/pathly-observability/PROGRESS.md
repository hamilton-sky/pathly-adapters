# Progress — pathly-observability

## Conversation status

| Conv | Title | Stories | Status | Gate |
|---|---|---|---|---|
| 1 | Python infrastructure | S-01, S-02, S-03 | DONE | `python -m pytest tests/ -q` |
| 2 | Skill phase logging | S-04, S-05, S-06 | DONE | Conv 1 tests green |
| 3 | design.md + storm.md phases | S-07 | DONE | none |
| 4 | Agent contracts + adapter propagation | S-08, S-09 | DONE | `pathly-setup claude --apply && pathly-setup codex --apply` |
| 5 | Pipeline auto-chain: fast→review + PROGRESS.md on pass | S-10, S-11 | DONE | `pathly-setup claude --apply` |

## Story completion

| Story | Title | Conv | Done |
|---|---|---|---|
| S-01 | Record phase start events via HTTP | 1 | [ ] |
| S-02 | Record phase done events via HTTP | 1 | [ ] |
| S-03 | Exempt-prefix support via flow YAML | 1 | [ ] |
| S-04 | Phase-boundary logging in build.md | 2 | [ ] |
| S-05 | Phase-boundary logging in review.md and test.md | 2 | [ ] |
| S-06 | Phase-boundary logging in plan.md + log-phase utility | 2 | [ ] |
| S-07 | Three-phase structure in design.md and storm.md | 3 | [ ] |
| S-08 | Rigor contract tables in agent files | 4 | [ ] |
| S-09 | stage_brief sections in agent files | 4 | [ ] |
| S-10 | fast/auto mode chains build → review | 5 | [ ] |
| S-11 | Reviewer marks conv DONE in PROGRESS.md on pass | 5 | [ ] |

## Notes

- Conv 2 is gated on Conv 1. Do not start Conv 2 until `python -m pytest tests/ -q` passes.
- Conv 3 is independent of Conv 2 and can run in parallel if needed.
- Conv 4 depends on Conv 2 and Conv 3 (agents should reference the log-phase utility correctly).
- Adapter propagation (Conv 4 post-steps) must run after all agent file edits are complete.
