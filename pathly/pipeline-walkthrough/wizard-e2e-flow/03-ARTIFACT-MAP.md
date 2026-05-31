# 03 — Artifact Map: wizard-e2e-flow

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| FEATURE_INDEX.md | Planner | All agents | File inventory — orientation guide |
| PO_NOTES.md | Planner / PO | Builder agents | Scope notes and decisions |
| VERIFY.md | Builder (manual) | FSM verify_gate | Build verification result |
| REVIEW.md | Reviewer | Tester | Review verdict and notes |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| REVIEW_FAILURES.md (attempt 1) | FSM verify_gate | Human (created VERIFY.md) | gate blocked: VERIFY.md missing |
| REVIEW_FAILURES.md (attempt 2) | FSM verify_gate | Human (created VERIFY.md) | gate blocked again before file propagated |
| HUMAN_QUESTIONS.md | FSM require_artifact | Human (confirmed no questions) | gate required artifact before TESTING |
| TEST_FAILURES_conv1_attempt1.md | Tester | Human review | AC4.2 step count mismatch; AC4.4 not covered |

---

## Source files changed

Files changed in pathly-adapters (Conv 1 — Studio testids):

| File | Stories | What changed |
|---|---|---|
| `studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx` | S1 / AC1.1 | Added `data-testid="sidebar-flows-add-btn"` to flow-section IconButton |
| `studio/src/renderer/src/components/FlowWizard/WizardFooter/WizardFooter.tsx` | S1 / AC1.2 | Added wizard-btn-cancel/back/next/save testids; added type="button" to Cancel, Back, Next |
| `studio/src/renderer/src/components/FlowWizard/Step0Entry/Step0Entry.tsx` | S1 / AC1.3 | Added wizard-start-template, wizard-start-blank, wizard-template-{id}, wizard-resume-draft |
| `studio/src/renderer/src/components/FlowWizard/Step1Name/Step1Name.tsx` | S1 / AC1.4 | Added wizard-input-name, wizard-input-description |
| `studio/src/renderer/src/components/FlowWizard/Step2States.tsx` | S1 / AC1.5 | (typecheck fix — minor prop forwarding adjustment) |

Files created in playwright-stepper-framework (Conv 2 — POM + glue + workflow):

| File | Stories | What changed |
|---|---|---|
| `poms/pathly/pages/wizard_page.py` | S2 | New: WizardPage(BasePage) with 9 locators and 5 action methods |
| `stepper/sites/pathly/pages/wizard_action.py` | S3 | New: PathlyWizard(PageModule) with 5 glue actions |
| `stepper/sites/pathly/workflows/pathly_wizard_smoke.json` | S4 | New: 10-step smoke workflow |
| `poms/pathly/__init__.py` | S2 | Modified: added WizardPage export |
| `stepper/sites/pathly/register.py` | S3 | Modified: registered PathlyWizard |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/wizard-e2e-flow/  ←── metrics record → this folder
```
