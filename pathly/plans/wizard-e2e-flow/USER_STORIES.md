---
name: User Stories
---
# wizard-e2e-flow — User Stories

## Context

The FlowWizard has zero `data-testid` attributes. No Stepper automation covers it.
This feature adds testids and wires up a Playwright-over-CDP smoke workflow that
drives the wizard from the sidebar trigger through all 5 steps to Save.

Same pattern as `stepper-pathly-ui`: first add stable selectors in Studio, then
add POM + glue + workflow in the stepper framework.

---

## S1 — data-testid attributes on FlowWizard

**As** Yafit, **I want** stable `data-testid` attributes on all interactive wizard
elements, **so that** the Stepper POM can target elements by testid without brittle CSS.

**Delivered by:** Conversation 1

### Acceptance criteria

- AC1.1: `LibraryPanel.tsx` has `data-testid="sidebar-flows-add-btn"` on the `IconButton`
  rendered for the flow section (the "+" button that opens the wizard).
- AC1.2: `WizardFooter.tsx` has `data-testid="wizard-btn-cancel"`, `"wizard-btn-back"`,
  `"wizard-btn-next"`, `"wizard-btn-save"` on the respective buttons.
- AC1.3: `Step0Entry.tsx` has `data-testid="wizard-start-template"` on the "From template"
  card, `"wizard-start-blank"` on the "Start blank" card, `"wizard-template-{id}"` on each
  named template button (using the template's `id` field), and `"wizard-resume-draft"` on
  the "Resume saved draft" button.
- AC1.4: `Step1Name.tsx` has `data-testid="wizard-input-name"` on the flow name `<input>`
  and `data-testid="wizard-input-description"` on the description `<textarea>` (or second
  input, whichever is used).
- AC1.5: Running `npm run typecheck` in the `studio/` directory passes with zero new errors.
- AC1.6: No existing class names, inline styles, or event handlers are modified — only
  `data-testid` props are added.

---

## S2 — WizardPage POM

**As** Yafit, **I want** a `WizardPage` POM class with locators bound to all AC1 testids,
**so that** glue actions and workflows call stable named methods.

**Delivered by:** Conversation 2

### Acceptance criteria

- AC2.1: `poms/pathly/pages/wizard_page.py` defines `WizardPage(BasePage)` with locators:
  `_flows_add_btn`, `_btn_cancel`, `_btn_back`, `_btn_next`, `_btn_save`,
  `_start_template`, `_start_blank`, `_input_name`, `_input_description`.
- AC2.2: Method `open_wizard()` — clicks `_flows_add_btn`.
- AC2.3: Method `select_template(template_id: str)` — clicks the template card with
  `[data-testid="wizard-template-{template_id}"]`.
- AC2.4: Method `set_name(name: str)` — fills `_input_name` with `name`.
- AC2.5: Method `click_next()` — clicks `_btn_next`.
- AC2.6: Method `click_save()` — clicks `_btn_save`.
- AC2.7: `url` property returns `"electron://pathly-wizard"`. `open()` is a no-op.
- AC2.8: All locators use `data-testid` selectors exclusively.

---

## S3 — Wizard glue actions

**As** Yafit, **I want** Stepper glue actions for the wizard, **so that** workflow JSON
files can call wizard steps by name.

**Delivered by:** Conversation 2

### Acceptance criteria

- AC3.1: `stepper/sites/pathly/pages/wizard_action.py` defines `PathlyWizard(PageModule)`
  with actions: `pathly_open_wizard`, `pathly_wizard_select_template`,
  `pathly_wizard_set_name`, `pathly_wizard_next`, `pathly_wizard_save`.
- AC3.2: `pathly_wizard_select_template` reads `extra.template_id` and fails the step if absent.
- AC3.3: `pathly_wizard_set_name` reads `extra.name` (fallback: `{{flow_name}}` variable).
- AC3.4: `stepper/sites/pathly/register.py` is updated to register `PathlyWizard`.
- AC3.5: Each action follows the `_execute(self, page, step, resolver, context, behaviour=None)`
  signature and returns `StepResult`.

---

## S4 — End-to-end smoke workflow

**As** Yafit, **I want** a runnable workflow JSON that opens the wizard, fills it out,
and saves a flow, **so that** I can verify the wizard is not broken before committing.

**Delivered by:** Conversation 2

### Acceptance criteria

- AC4.1: `stepper/sites/pathly/workflows/pathly_wizard_smoke.json` is valid workflow JSON
  (`{name, description, variables, steps}`).
- AC4.2: The workflow steps in order:
  1. Wait for Electron ready (short wait step)
  2. `pathly_open_wizard` — click the "+" in the flows section
  3. `pathly_wizard_select_template` with `template_id: "standard-pipeline"` (first template)
  4. `pathly_wizard_set_name` with `name: "{{flow_name}}"` variable
  5. `pathly_wizard_next` — advance through steps 2, 3, 4, 5 (4 clicks)
  6. `pathly_wizard_save` — click Save Flow
  7. `screenshot` — capture result
- AC4.3: Default `variables.flow_name` is `"test-automation-flow"`.
- AC4.4: If the flow name is already taken (file exists), the workflow is idempotent —
  it overwrites the file (Studio's `writeFile` overwrites without prompting).
