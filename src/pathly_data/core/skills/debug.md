# debug

This is the canonical, tool-agnostic Pathly behavior for the debug workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use route `debug <symptom-name>` when:
- A bug is observed (symptom is known) but the root cause is not
- You need a traceable, auditable fix with before/after test evidence
- The bug is in production code (not a plan/pipeline issue — use `verify-state` for that)

Do NOT use for exploratory questions ("how does X work?") — use `explore` instead.
Do NOT use when you already know the fix — just fix it directly.

---

## File structure

```
pathly/debugs/<symptom-name>/
  SYMPTOM.md       ← what broke, how it manifests, environment
  REPRO.md         ← minimal steps to reproduce
  ROOT_CAUSE.md    ← what the root cause is (written by scout/builder)
  FIX.md           ← what changed and why
  feedback/
    HUMAN_QUESTIONS.md   ← blocks on user decision
    TEST_FAILURES.md     ← tester → builder (same protocol as team)
```

---

## Step 1 — Capture the symptom

If `$ARGUMENTS` is blank: ask "Describe the bug symptom in a few words (used as folder name)."

Store the symptom name as `SYMPTOM_NAME`.

Ask the user to fill in `SYMPTOM.md`. If the user already described it in the debug invocation, pre-fill it:

```markdown
# Symptom — <symptom-name>

## What broke
[observable behavior — what is wrong]

## How it manifests
[error message, stack trace, wrong output, screenshot — paste exactly]

## Environment
[branch, commit, OS, relevant config]

## Expected behavior
[what should happen instead]
```

Confirm the symptom is written before continuing.

---

## Spawn orchestrator

Spawn the **orchestrator** agent with:
- flow_config: src/pathly_data/core/flows/debug.flow.yaml
- topic: [SYMPTOM_NAME]
- rigor: lite
- autoFlow: [autoFlow]

The orchestrator drives the full debug pipeline (investigate → reproduce → fix → verify → review)
using the FSM defined in `debug.flow.yaml`. It handles all state tracking, agent spawning,
and feedback routing. Do not perform these actions in debug.md.
