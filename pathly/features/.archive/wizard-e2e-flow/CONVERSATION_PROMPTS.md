---
name: Conversation Guide
---
# wizard-e2e-flow — Conversation Guide

2 conversations. Commit pathly-adapters after Conv 1 before starting Conv 2.

---

## Conversation 1 — data-testid attributes (pathly-adapters)

Stories: S1

```text
Read pathly/plans/wizard-e2e-flow/FEATURE_INDEX.md to orient yourself.

Implement wizard-e2e-flow Conversation 1 from pathly/plans/wizard-e2e-flow/IMPLEMENTATION_PLAN.md.

Working repo: pathly-adapters (studio/).

Files to modify:
  studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx
  studio/src/renderer/src/components/FlowWizard/WizardFooter/WizardFooter.tsx
  studio/src/renderer/src/components/FlowWizard/Step0Entry/Step0Entry.tsx
  studio/src/renderer/src/components/FlowWizard/Step1Name/Step1Name.tsx

Read each file first, then add only data-testid props as specified in the plan.
No other changes — no style edits, no logic changes.

Testids to add:
  LibraryPanel.tsx — sidebar-flows-add-btn (on the "+" IconButton for the flow section)
  WizardFooter.tsx — wizard-btn-cancel, wizard-btn-back, wizard-btn-next, wizard-btn-save
  Step0Entry.tsx  — wizard-start-template, wizard-start-blank, wizard-template-{id}, wizard-resume-draft
  Step1Name.tsx   — wizard-input-name, wizard-input-description

After adding testids, check if IconButton and the Button component in WizardFooter
forward a data-testid prop through to the inner <button>. If not, add the prop to
their TypeScript interface and forward it. Only change what is strictly necessary.

Verify:
  npm run typecheck   (from repo root, not studio/)
Zero new TypeScript errors. Fix any that arise from the prop additions.

Update pathly/plans/wizard-e2e-flow/PROGRESS.md Conv 1 to DONE.
Commit the changes.
```

---

## Conversation 2 — POM + glue + workflow (playwright-stepper-framework)

Stories: S2, S3, S4

**Prerequisite:** Conv 1 committed.

```text
Read pathly/plans/wizard-e2e-flow/FEATURE_INDEX.md to orient yourself.

Implement wizard-e2e-flow Conversation 2 from pathly/plans/wizard-e2e-flow/IMPLEMENTATION_PLAN.md.

Working repo: playwright-stepper-framework.

Files to create:
  poms/pathly/pages/wizard_page.py
  stepper/sites/pathly/pages/wizard_action.py
  stepper/sites/pathly/workflows/pathly_wizard_smoke.json

Files to modify:
  poms/pathly/__init__.py  — export WizardPage
  stepper/sites/pathly/register.py  — call PathlyWizard.register(registry)

Follow the patterns established in poms/pathly/pages/home_screen_page.py (POM)
and stepper/sites/pathly/pages/home_screen_action.py (glue) exactly.

Naming:
  POM: WizardPage(BasePage), poms/pathly/pages/wizard_page.py
  Glue module: PathlyWizard(PageModule), wizard_action.py
  Actions: pathly_open_wizard, pathly_wizard_select_template,
           pathly_wizard_set_name, pathly_wizard_next, pathly_wizard_save

Workflow: pathly_wizard_smoke.json — steps as specified in IMPLEMENTATION_PLAN.md.
Use "wait" action for the initial 1000ms wait (if a wait glue action exists),
otherwise use a screenshot + comment. Do not invent non-existent actions.

Verify:
  cd stepper && python -m pytest tests/unit/ -q
All existing unit tests pass. No new test file required for this conversation.

Update pathly/plans/wizard-e2e-flow/PROGRESS.md Conv 2 to DONE.
Commit the changes.
```
