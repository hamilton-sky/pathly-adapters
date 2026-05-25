---
name: Retrospective
---
# studio-polish — Retrospective

**Feature:** studio-polish | **Completed:** 2026-05-25 | **Branch:** master

---

## What Was Built

studio-polish delivered 6 user stories across 4 conversations, improving UI/UX responsiveness, preventing data loss, and establishing testing infrastructure:

- **Conv 1 — S1/S2/S3 (Button + FlowEditor + YAML):** Button loading prop + font fix; FlowEditor shimmer skeleton loader; YAML parse error line numbers; FlowWizard save button loading state.
- **Conv 2 — S4 (Navigation guard):** Unsaved-changes confirmation modal in FlowEditor — prevents accidental navigation away from dirty `.flow.yaml` files.
- **Conv 3 — S5 (Vitest suite):** 8 passing tests covering `useFlowFile` hook (load, error, parse error, save) and `validateFlow` (valid flow, missing state target, unknown behavior, bad transition_rules.default).
- **Conv 4 — S6 (CLI refactor):** Split `setup_command.py` into `cli.py` (main + interactive menu) + `orchestrate.py` (host runner + codegen helpers) using thin shim pattern.

**Build results:** npm build passes · 177 pytest pass (6 pre-existing failures, 0 new) · 8 vitest tests pass

---

## What Went Well

- Clean separation of UI polish (Conv 1–2) and infrastructure (Conv 3–4) allowed focused, non-overlapping review cycles.
- Architecture review caught the structural violation (main() left in wrong module) in one feedback loop — the review stage paid for itself.
- All 6 stories delivered with zero regressions across both frontend (TypeScript build) and backend (pytest) test suites.
- Scout phase surfaced key deviations from the plan (WizardFooter vs FlowWizard, inline styles vs CSS module, dead `yamlParseError` field) before the builder touched any code — saved at least one fix cycle.

## What Was Rough

- **ARCH_FEEDBACK on Conv 4:** Builder left `main()` in `setup_command.py` rather than moving it to `cli.py`. One architect + builder cycle to correct. Root cause: the shim responsibility was implicit in the plan rather than explicit in the story.
- **Pyright re-export:** After creating the shim, a `from .cli import main` required `from .cli import main as main` for Pyright to recognize the re-export across the module boundary. Minor but not obvious.
- **FSM state bootstrapping:** Feature had pre-existing plan files but no STATE.json/EVENTS.jsonl — required manual state initialization before the first FSM call.

---

## Lessons

1. **Thin-shim refactors need explicit per-file responsibility lists in the plan.** "module becomes a shim" is ambiguous — state which file owns each function by name before building.
2. **Pyright re-export pattern:** use `from .x import y as y` (not `from .x import y`) in shim files to satisfy strict Pyright `reportMissingImports` checks.
3. **Scout phase before builder is high-ROI** for conversations touching files the plan was written against — actual file structure often diverges from plan assumptions.
