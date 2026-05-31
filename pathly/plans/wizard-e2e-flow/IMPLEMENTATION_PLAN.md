---
name: Implementation Plan
---
# wizard-e2e-flow — Implementation Plan

## Overview

Cross-repo Stepper automation for the FlowWizard. Two conversations:
- Conv 1: add testids in Studio (pathly-adapters)
- Conv 2: POM + glue + workflow in playwright-stepper-framework

Same pattern as `stepper-pathly-ui`. Conv 2 depends on Conv 1 being committed.

---

## Conv 1 — data-testid attributes (pathly-adapters)

**Stories:** S1

**Files to modify:**

### `studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx`

Find the `renderSection` function. Where `section.type === 'flow'` the `IconButton`
for `onNewUserLibraryItem` is rendered. Add `data-testid="sidebar-flows-add-btn"` to
that `IconButton`. The other sections share the same render path — use a conditional
or a separate prop on the IconButton so only the flow section gets this testid, e.g.:
```tsx
<IconButton
  data-testid={section.type === 'flow' ? 'sidebar-flows-add-btn' : undefined}
  onClick={(e) => onNewUserLibraryItem(section, e)}
  title={`New ${displayLabel.slice(0,-1).toLowerCase()}`}
>
```
Check how `IconButton` forwards props — if it doesn't spread `data-testid`, add a
`data-testid` prop to `IconButton`'s interface and forward it to the inner `<button>`.

### `studio/src/renderer/src/components/FlowWizard/WizardFooter/WizardFooter.tsx`

Add testids to the four buttons:
```tsx
<button ... data-testid="wizard-btn-cancel">Cancel</button>
<button ... data-testid="wizard-btn-back">← Back</button>
<button ... data-testid="wizard-btn-next">Next →</button>
<Button ... data-testid="wizard-btn-save">Save Flow</Button>
```
For the `Button` component, check if it accepts and forwards `data-testid` — add the
prop to Button's interface if needed, or use a wrapper `<span data-testid="wizard-btn-save">`.

### `studio/src/renderer/src/components/FlowWizard/Step0Entry/Step0Entry.tsx`

```tsx
<button type="button" data-testid="wizard-start-template" ...>From template</button>
<button type="button" data-testid="wizard-start-blank" ...>Start blank</button>
{/* per-template button: */}
<button key={template.id} type="button" data-testid={`wizard-template-${template.id}`} ...>
<button type="button" data-testid="wizard-resume-draft" ...>Resume saved draft</button>
```

### `studio/src/renderer/src/components/FlowWizard/Step1Name/Step1Name.tsx`

Read the file to find the name `<input>` and description field. Add:
```tsx
<input ... data-testid="wizard-input-name" />
<textarea ... data-testid="wizard-input-description" />
```

**Verify after Conv 1:**
```bash
npm run typecheck   # from repo root
```
Zero new errors. Do not run tests (no new tests are added in Conv 1).

---

## Conv 2 — POM + glue + workflow (playwright-stepper-framework)

**Stories:** S2, S3, S4

**Prerequisite:** Conv 1 committed to pathly-adapters.

### `poms/pathly/pages/wizard_page.py`

```python
class WizardPage(BasePage):
    url = "electron://pathly-wizard"

    async def open(self): pass  # no-op

    @property
    def _flows_add_btn(self): return self._page.locator('[data-testid="sidebar-flows-add-btn"]')
    @property
    def _btn_next(self): return self._page.locator('[data-testid="wizard-btn-next"]')
    @property
    def _btn_back(self): return self._page.locator('[data-testid="wizard-btn-back"]')
    @property
    def _btn_cancel(self): return self._page.locator('[data-testid="wizard-btn-cancel"]')
    @property
    def _btn_save(self): return self._page.locator('[data-testid="wizard-btn-save"]')
    @property
    def _start_template(self): return self._page.locator('[data-testid="wizard-start-template"]')
    @property
    def _start_blank(self): return self._page.locator('[data-testid="wizard-start-blank"]')
    @property
    def _input_name(self): return self._page.locator('[data-testid="wizard-input-name"]')
    @property
    def _input_description(self): return self._page.locator('[data-testid="wizard-input-description"]')

    def template(self, template_id: str):
        return self._page.locator(f'[data-testid="wizard-template-{template_id}"]')

    async def open_wizard(self): await self._flows_add_btn.click()
    async def select_template(self, template_id: str): await self.template(template_id).click()
    async def set_name(self, name: str):
        await self._input_name.click()
        await self._input_name.fill(name)
    async def click_next(self): await self._btn_next.click()
    async def click_save(self): await self._btn_save.click()
```

### `poms/pathly/__init__.py`

Add `from poms.pathly.pages.wizard_page import WizardPage` export.

### `stepper/sites/pathly/pages/wizard_action.py`

Five actions in `PathlyWizard(PageModule)`:
- `pathly_open_wizard` — calls `wizard.open_wizard()`
- `pathly_wizard_select_template` — reads `extra.template_id`, calls `wizard.select_template(id)`
- `pathly_wizard_set_name` — reads `extra.name` (fallback: step variable `flow_name`),
  calls `wizard.set_name(name)`
- `pathly_wizard_next` — calls `wizard.click_next()`
- `pathly_wizard_save` — calls `wizard.click_save()`

### `stepper/sites/pathly/register.py`

Add `PathlyWizard.register(registry)`.

### `stepper/sites/pathly/workflows/pathly_wizard_smoke.json`

```json
{
  "name": "pathly-wizard-smoke",
  "description": "Smoke-test the FlowWizard end-to-end: open → template → name → navigate → save.",
  "variables": { "flow_name": "test-automation-flow" },
  "steps": [
    { "action": "wait", "description": "Wait for Electron renderer", "extra": { "ms": 1000 } },
    { "action": "pathly_open_wizard", "description": "Click '+' in User Flows sidebar section" },
    { "action": "pathly_wizard_select_template", "description": "Select standard-pipeline template",
      "extra": { "template_id": "standard-pipeline" } },
    { "action": "pathly_wizard_set_name", "description": "Enter flow name",
      "extra": { "name": "{{flow_name}}" } },
    { "action": "pathly_wizard_next", "description": "Advance: step 1 → 2 (States)" },
    { "action": "pathly_wizard_next", "description": "Advance: step 2 → 3 (Transitions)" },
    { "action": "pathly_wizard_next", "description": "Advance: step 3 → 4 (Agents)" },
    { "action": "pathly_wizard_next", "description": "Advance: step 4 → 5 (Review)" },
    { "action": "pathly_wizard_save", "description": "Click Save Flow" },
    { "action": "screenshot", "description": "Capture post-save state" }
  ]
}
```

**Verify after Conv 2:**
```bash
cd stepper
python -m pytest tests/unit/ -q
```
No regressions in existing unit tests.
