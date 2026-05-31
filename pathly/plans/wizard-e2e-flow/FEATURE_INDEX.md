---
name: wizard-e2e-flow
type: stepper-automation
repos: [pathly-adapters, playwright-stepper-framework]
---
# wizard-e2e-flow — Feature Index

Stepper automation workflow that drives the Pathly FlowWizard end-to-end:
open → select template → name the flow → step through all 5 steps → save.

Same cross-repo pattern as `stepper-pathly-ui`.

## Conversations

| Conv | Repo | Deliverable |
|---|---|---|
| 1 | pathly-adapters | `data-testid` on wizard trigger, footer nav buttons, step-0 cards, step-1 inputs |
| 2 | playwright-stepper-framework | `WizardPage` POM + `wizard_action.py` glue + `pathly_wizard_smoke.json` |

## Key files

### pathly-adapters (Studio)
- `studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx` — add `data-testid` on flow "+" IconButton
- `studio/src/renderer/src/components/FlowWizard/WizardFooter/WizardFooter.tsx` — testids on Cancel/Back/Next/Save
- `studio/src/renderer/src/components/FlowWizard/Step0Entry/Step0Entry.tsx` — testids on template/blank/resume cards
- `studio/src/renderer/src/components/FlowWizard/Step1Name/Step1Name.tsx` — testids on name + description inputs

### playwright-stepper-framework
- `poms/pathly/pages/wizard_page.py` — WizardPage(BasePage)
- `stepper/sites/pathly/pages/wizard_action.py` — PathlyWizard glue module
- `stepper/sites/pathly/register.py` — register PathlyWizard
- `stepper/sites/pathly/workflows/pathly_wizard_smoke.json` — E2E smoke workflow

## data-testid naming convention

```
sidebar-flows-add-btn          ← "+" in the User Flows section header
wizard-btn-cancel
wizard-btn-back
wizard-btn-next
wizard-btn-save
wizard-start-template          ← "From template" card on step 0
wizard-start-blank             ← "Start blank" card on step 0
wizard-template-{id}           ← each named template card (kebab id)
wizard-resume-draft            ← "Resume saved draft" button on step 0
wizard-input-name              ← flow name <input> on step 1
wizard-input-description       ← description <textarea> on step 1
```

## Run smoke workflow

```bash
cd stepper
python main.py --browser electron --cdp-port 9222 \
  --workflow sites/pathly/workflows/pathly_wizard_smoke.json \
  --vars '{"flow_name":"test-flow"}'
```
