# PO Notes — pathly-adapters

_Last updated: 2026-06-29_

## Who Is This For

**Primary users:** solo developers and small teams who want to run autonomous, headless multi-agent software development pipelines from their local machine — specifically those using Claude Code as the CLI engine. The human acts as a supervisor through the visual **Command Center** (Studio), setting goals, answering escalated questions, and reviewing artifacts; the system does the per-step agent work autonomously.

**Secondary users:** the framework author (Hamilton) who is simultaneously the user and the maintainer — meaning every design decision is immediately dog-fooded on the real product.

## Definition of Success

The pathly-adapters framework is successful when:

1. **End-to-end headless runs complete without manual intervention** — a goal entered in Studio travels through STORM → PLAN → DESIGN → BUILD → REVIEW → TEST → RETRO → DONE with the supervisor driving agent spawns, collecting results, and advancing the FSM without human action per step.
2. **The board is the substrate** — every agent reads from and writes to the comms board so that context is preserved across stages and the human can audit the full decision trail from Studio.
3. **Adapters are first-class** — `pathly-setup <host> --apply` installs a working, complete skill + agent set to any of the four supported CLIs (claude, codex, copilot, antigravity); each pipeline stage runs on the adapter best suited to that stage's compute profile.
4. **Operators can move fast** — a developer can start a new feature, run the full pipeline, and land a reviewed+tested implementation with ≤ 3 human interactions (goal entry, architecture decision, final merge approval).

The one outcome that matters most: **a headless run on the real FSM advances through ≥ 2 consecutive pipeline stages without human intervention**, reliably, on the current codebase.

## Out of Scope

- **Models / Brightsky / WebSocket** — split into their own plan (`project_models_separate_from_cli` memory); intentionally deferred until CLI-composition work stabilises.
- **P3 parallel worktree fan-in** — the cross-goal parallel execution layer is deferred until P1 interactive board is solid.
- **WebGPU / WebLLM in Electron** — ruled out; Electron's renderer sandbox blocks it. Local inference must go through Ollama or node-llama-cpp v3.
- **Cursor adapter** — needs WSL2 on Windows; separate plan.
- **CrewAI / LangGraph compatibility** — not a target; Pathly is local-first and methodology-centric, not a Python framework.
- **Any specific feature currently tracked in another plan** (md-diagram-conversion, spawn-scheduler, ai-action-config, etc.) — those ship on their own tracks.

## Constraints

- **FSM correctness is non-negotiable** — the `next_state` contract and `convs_done` overwrite bugs (fixed 2026-06-28) demonstrated that mock tests on both sides of the FSM↔driver boundary hide real failures. Any FSM change must be verified by driving the real FSM through ≥ 1 real transition.
- **SOLID / 400-line limit** — all Python in `src/pathly_orchestrator/` and TypeScript in `studio/src/` must respect the 400-line-per-file hard limit and single-responsibility rules; ongoing refactor (e5027a82) enforces this.
- **No push to master without explicit request** — branch workflow: develop on a feature branch, confirm target before any push.
- **Windows-first runtime** — Studio runs on Windows 11; headless argv must be encoded as PowerShell temp-scripts; `codex` headless pipes `$null` as stdin. Linux/macOS portability is nice-to-have, not gating.
- **Adapter sync rule** — any change to `core/` agents or skills must propagate to all four adapter `_meta/` directories via `pathly-setup claude --apply --repair` + `python -m build`; stale adapters are a known operational risk.
- **Readiness baseline (2026-06-28):** 32-agent assessment verdict — "usable-with-significant-gaps". Cut list: defer differ/LSP, defer code-intel and parallel fleet. Design-without-build pattern validated. Full assessment in `pathly/plans/readiness-assessment-2026-06/`.

## Open Questions

1. **Consultation flow trigger** — what specific topic or improvement prompted this consultation? The FSM launched `consultation` with `topic=pathly-adapters` but no SPEC.md or STORM_SEED.md was provided. Working assumption: this is a **framework-health planning session** — scoping what gaps to close next based on the readiness assessment and current in-flight work. If the intent was a specific sub-feature, the human should post a clarification to the board; proceeding on the framework-health assumption.

2. **Rigor level** — given the framework author is the only active user, `standard` rigor (plan+build+review+test) is the assumed default. `strict` (adds audit) may be appropriate if the session targets the FSM core or the supervisor. Proceeding with `standard`.
