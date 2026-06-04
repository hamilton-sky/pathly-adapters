# 01-PIPELINE-FLOW.md — agent-done-early-advance

**Date:** 2026-06-04  
**Branch:** master  
**User intent:** Implement early FSM advance when agent writes AGENT_DONE to EVENTS.jsonl mid-run, without waiting for PTY exit.

---

## FSM State Sequence

```
PLAN → BUILDING (conv 1) → REVIEWING → BUILDING (conv 2) → REVIEWING
     → BUILDING (conv 3) → REVIEWING → BUILDING (conv 4) → REVIEWING
     → BUILDING (conv 5) → REVIEWING → TESTING → RETRO → DONE
```

| # | From | To | Timestamp |
|---|---|---|---|
| 1 | — | PLAN | 2026-06-03T22:19 |
| 2 | PLAN | BUILDING | 2026-06-03T22:19 |
| 3 | BUILDING | REVIEWING | 2026-06-03T22:28 |
| 4 | REVIEWING | BUILDING | 2026-06-03T22:32 |
| 5 | BUILDING | REVIEWING | 2026-06-03T22:47 |
| 6 | REVIEWING | BUILDING | 2026-06-03T22:52 |
| 7 | BUILDING | REVIEWING | 2026-06-03T23:15 |
| 8 | REVIEWING | BUILDING | 2026-06-03T23:21 |
| 9 | BUILDING | REVIEWING | 2026-06-03T23:27 |
| 10 | REVIEWING | BUILDING | 2026-06-03T23:29 |
| 11 | BUILDING | REVIEWING | 2026-06-03T23:33 |
| 12 | REVIEWING | TESTING | 2026-06-03T23:42 |
| 13 | TESTING | RETRO | 2026-06-03T23:55 |
| 14 | RETRO | DONE | 2026-06-04 |

---

## Conversation Traces

### Conv 1 — Foundation layer (events, runner, feature flag)
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| BUILD | builder | DONE | 418s | 47,778 |
| REVIEW | reviewer | PASS | 49s | 51,581 |

Summary: TYPE_STAGE_RECONCILIATION_FAILURE, FeatureFlags.early_advance, tail_agent_done(); 396 tests pass.

### Conv 2 — Supervisor watcher + reconciliation + tests
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| BUILD | builder | DONE | 820s | 164,080 |
| REVIEW | reviewer | PASS | 99s | 34,982 |

Summary: _agent_done_events dicts, _agent_done_watcher, _reconciliation_window, fast-path branch, 3 new supervisor tests; 399 tests pass.

### Conv 3 — Studio SSE pill (TERMINAL_AGENT_DONE + finalizing status)
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| BUILD | builder | DONE | — | not captured |
| REVIEW | reviewer | PASS | 309s | 53,204 |

Summary: TERMINAL_AGENT_DONE broadcast, RunnerStatus 'finalizing', StageStatusStrip dotFinalizing CSS, useHQ routing; 399 tests pass.

*Note: billing-update fix (TYPE_BILLING_UPDATE, _patch_last_agent_done, mergeBillingUpdate, useMonitorSession routing) interleaved during Conv 2-3.*

### Conv 4 — Interactive mode (visible PTY + kill on AGENT_DONE)
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| BUILD | builder | DONE | 235s | not captured |
| REVIEW | reviewer | PASS | 117s | 34,220 |

Summary: TYPE_STAGE_INTERACTIVE_DONE, FeatureFlags.interactive, resolve_argv guard, startup guard, _cleanup_run_id, fast-path interactive kill; 401 tests pass.

### Conv 5 — Pipeline History context injection
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| BUILD | builder | DONE | 165s | not captured |
| REVIEW | reviewer | PASS | 108s | 22,503 |

Summary: build_pipeline_history_block(), build_prompt history append in fsm_ops, 3 new tests; 404 tests pass.

### Testing stage
| Stage | Agent | Result | Wall | Tokens |
|---|---|---|---|---|
| TEST | tester | PASS | 790s | 40,018 |

Summary: All 8 user stories verified PASS across 404 tests; no TEST_FAILURES.md written.

---

## Feedback Loops

| Conv | File | Type | Retry | Resolution |
|---|---|---|---|---|
| — | HUMAN_QUESTIONS.md | require_artifact gate (REVIEW.md missing at REVIEWING→TESTING) | 0 | REVIEW.md created; resolved-file flag on complete-stage |

No REVIEW_FAILURES or TEST_FAILURES rounds.
