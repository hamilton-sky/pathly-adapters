# 03 — Artifact Map: multi-adapter-runner

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| feedback/REVIEW_FAILURES.md | Reviewer (round 1) | Builder (fix pass) | 3 violations: hardcoded adapter in parse_result, missing run_id in /runner/start, input() in handle_decide headless path |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/core/adapters.yaml` | S1 | New adapter command map: claude/codex/copilot with terminal_kind, headless argv, autonomy_flag, resume, parse fields |
| `src/pathly_orchestrator/adapters.py` | S1 | `resolve_command(adapter, prompt, model, session) → {argv, terminal_kind, supports_resume}` |
| `scripts/gen_adapters_ts.py` | S1 | Generator: reads adapters.yaml, writes studio/src/renderer/src/lib/adapters.gen.ts |
| `studio/src/renderer/src/lib/adapters.gen.ts` | S1 | Generated TypeScript mirror of adapters.yaml (anti-drift test validates) |
| `src/pathly_orchestrator/runner.py` | S1, S3 | `resolve_argv()` extracted from invoke_agent; `parse_result(adapter, raw)` extracted; `handle_decide(interactive=True)` raises RuntimeError when headless |
| `src/pathly_orchestrator/supervisor.py` | S2, S3 | `RunnerState` dataclass + in-memory registry; threaded run loop; pause/abort/cap enforcement; session continuity; RUNNER_STATE.json mirror; `run_id` UUID field |
| `src/pathly_orchestrator/http_server.py` | S3 | 8 POST control endpoints + GET /runner/status + GET /events/runner SSE + /runner/terminal/started + /runner/terminal/result; `run_id` in /runner/start response; adapter-aware parse_result call |
| `tests/test_adapters.py` | S1 | adapters.yaml shape, resolve_command, copilot raises, anti-drift test |
| `tests/test_supervisor.py` | S2 | RunnerState fields, loop/caps/abort/decision/session/mirror tests |
| `tests/test_runner_endpoints.py` | S3 | All 8+ endpoint tests + SSE + terminal endpoint 404 cases |
| `tests/test_runner.py` | S1, S3 | resolve_argv, parse_result (6 parametrized cases), handle_decide |

---

## Artifact flow diagram

```
adapters.yaml                 ←── declarative source of truth
      │
      ├──► adapters.py (resolve_command)
      │         │
      │         └──► runner.py (resolve_argv → invoke_agent)
      │                   │
      │                   └──► supervisor.py (_loop → _run_stage_via_terminal)
      │                              │
      │                              └──► http_server.py (endpoints + SSE)
      │
      └──► gen_adapters_ts.py → adapters.gen.ts (Studio reads for UI)
```
