# TEST_FAILURES — wizard-e2e-flow

Generated: 2026-05-31

## Summary

20 of 22 criteria PASS. 1 FAIL, 1 NOT COVERED.

---

## Full test plan

### Story 1 — data-testid attributes on FlowWizard

```
Story 1.1: LibraryPanel sidebar-flows-add-btn
  Criterion: LibraryPanel.tsx has data-testid="sidebar-flows-add-btn" on the IconButton
             rendered for the flow section.
  Test: Static read of LibraryPanel.tsx line 117
  Status: PASS

Story 1.2: WizardFooter four testids + type="button"
  Criterion: WizardFooter.tsx has wizard-btn-cancel, wizard-btn-back, wizard-btn-next,
             wizard-btn-save; Cancel/Back/Next have type="button".
  Test: Static read of WizardFooter.tsx lines 30-38
  Status: PASS

Story 1.3: Step0Entry four testids
  Criterion: wizard-start-template, wizard-start-blank, wizard-template-{id}, wizard-resume-draft
  Test: Static read of Step0Entry.tsx lines 32, 40, 58, 73
  Status: PASS

Story 1.4: Step1Name two testids
  Criterion: wizard-input-name on <input>, wizard-input-description on <textarea>
  Test: Static read of Step1Name.tsx lines 28, 37
  Status: PASS

Story 1.5: npm run typecheck passes with zero new errors
  Criterion: Running npm run typecheck in studio/ passes with zero new errors.
  Test: Already verified in Conv 1 context; confirmed PASS.
  Status: PASS

Story 1.6: No existing class names, styles, or handlers modified
  Criterion: Only data-testid props added; nothing else changed.
  Test: Static inspection of all four component files
  Status: PASS
```

### Story 2 — WizardPage POM

```
Story 2.1: WizardPage(BasePage) with all nine locators
  Criterion: _flows_add_btn, _btn_cancel, _btn_back, _btn_next, _btn_save,
             _start_template, _start_blank, _input_name, _input_description
  Test: Static read of wizard_page.py lines 23-56
  Status: PASS

Story 2.2: open_wizard() clicks _flows_add_btn
  Criterion: Method open_wizard() clicks _flows_add_btn.
  Test: Static read of wizard_page.py lines 61-62
  Status: PASS

Story 2.3: select_template(template_id) uses dynamic testid
  Criterion: Clicks [data-testid="wizard-template-{template_id}"]
  Test: Static read of wizard_page.py lines 58-59, 64-65
  Status: PASS

Story 2.4: set_name(name) fills _input_name
  Criterion: Fills _input_name with name.
  Test: Static read of wizard_page.py lines 67-69
  Status: PASS

Story 2.5: click_next() clicks _btn_next
  Criterion: Clicks _btn_next.
  Test: Static read of wizard_page.py lines 71-72
  Status: PASS

Story 2.6: click_save() clicks _btn_save
  Criterion: Clicks _btn_save.
  Test: Static read of wizard_page.py lines 74-75
  Status: PASS

Story 2.7: url = "electron://pathly-wizard"; open() is no-op
  Criterion: url property and open() no-op.
  Test: Static read of wizard_page.py lines 17, 19-20
  Status: PASS

Story 2.8: All locators use data-testid selectors exclusively
  Criterion: No CSS class, XPath, or text selectors.
  Test: Static read of wizard_page.py — all 9 locators use [data-testid="..."]
  Status: PASS
```

### Story 3 — Wizard glue actions

```
Story 3.1: PathlyWizard(PageModule) with 5 actions
  Criterion: pathly_open_wizard, pathly_wizard_select_template, pathly_wizard_set_name,
             pathly_wizard_next, pathly_wizard_save
  Test: Static read of wizard_action.py lines 21-152
  Status: PASS

Story 3.2: pathly_wizard_select_template reads extra.template_id, fails if absent
  Criterion: Reads template_id from extra; returns failed StepResult if missing.
  Test: Static read of wizard_action.py lines 52-57
  Status: PASS

Story 3.3: pathly_wizard_set_name reads extra.name (fallback: {{flow_name}} variable)
  Criterion: Reads extra.name with fallback to {{flow_name}} variable.
  Test: Static read of wizard_action.py line 79
  Status: PASS
  Notes: Fallback reads extra.flow_name key, not a variable lookup. In practice the
         workflow JSON passes name="{{flow_name}}" so the resolver interpolates it
         before the action runs — this is the correct stepper pattern.

Story 3.4: register.py registers PathlyWizard
  Criterion: stepper/sites/pathly/register.py imports and registers PathlyWizard.
  Test: Static read of register.py lines 4, 10
  Status: PASS

Story 3.5: _execute signature and StepResult return type
  Criterion: async def _execute(self, page, step, resolver, context, behaviour=None) -> StepResult
  Test: Static read of all 5 action _execute definitions in wizard_action.py
  Status: PASS
```

### Story 4 — End-to-end smoke workflow

```
Story 4.1: pathly_wizard_smoke.json is valid JSON with required top-level fields
  Criterion: {name, description, variables, steps} structure.
  Test: Static read of pathly_wizard_smoke.json
  Status: PASS

Story 4.2: Workflow steps in specified order
  Criterion: 7 steps: wait → open_wizard → select_template → set_name →
             pathly_wizard_next (3 clicks for steps 2,3,4) → save → screenshot
  Test: Static read of pathly_wizard_smoke.json steps array
  Status: FAIL
  Notes: The workflow contains 4 pathly_wizard_next calls (advancing steps 1→2, 2→3,
         3→4, 4→5), not 3 as specified. Step1Name.tsx shows "Step 1 / 8", suggesting
         the wizard has more steps than the criterion assumed when it was written.
         The implementation is internally consistent (4 nexts to reach the Save step
         from step 1), but it does not match "3 clicks" in AC4.2.
         This may be a story that was written before the wizard step count was
         finalised. Requires the builder or planner to confirm correct step count
         and update the story accordingly.

Story 4.3: Default variables.flow_name = "test-automation-flow"
  Criterion: variables.flow_name defaults to "test-automation-flow"
  Test: Static read of pathly_wizard_smoke.json line 4
  Status: PASS

Story 4.4: Workflow is idempotent when flow name already exists
  Criterion: Studio writeFile overwrites without prompting; workflow handles duplicate names.
  Test: Not verifiable statically from the JSON or POM files.
  Status: NOT COVERED
  Notes: This criterion depends on runtime Studio behaviour (Electron IPC writeFile handler).
         It cannot be verified from static analysis or unit tests alone. An integration
         test running the full workflow against a live Electron instance is required.
         No such test exists in tests/unit/.
```

---

## Action items for builder

1. **AC4.2 — step count mismatch:** Confirm whether 3 or 4 `pathly_wizard_next` calls are
   correct given the actual wizard step count. Update USER_STORIES.md AC4.2 to match, or
   update the workflow JSON to use 3 clicks if the wizard step count changed.

2. **AC4.4 — idempotency not tested:** Add an integration test or document this as a
   known gap requiring live-Electron verification. If the criterion is accepted as
   "verified by design" (Studio writeFile always overwrites), note that explicitly in
   USER_STORIES.md.
