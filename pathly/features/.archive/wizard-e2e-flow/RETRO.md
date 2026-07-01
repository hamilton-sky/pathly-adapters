---
feature: wizard-e2e-flow
stage: RETRO
date: 2026-05-31
---
# Retrospective — wizard-e2e-flow

## What went well

**Pattern reuse worked.** The two-phase pattern established by `stepper-pathly-ui` (testids first
in Studio, then POM + glue + workflow in the stepper framework) transferred cleanly. Conv 1 and
Conv 2 followed the same structure with minimal deviation. The plan files were complete enough
that both builder conversations required no IMPL_QUESTIONS clarification.

**Reviewer caught a real pre-existing violation.** The reviewer flagged that three `WizardFooter`
buttons were missing `type="button"` — a pre-existing gap that the testid additions exposed to
code review. The fix was incorporated before merging. This demonstrates the value of review even
on apparently low-risk testid-only changes.

**POM locator completeness was solid.** All nine WizardPage locators were implemented and verified
in a single conversation. The grep-based done-condition lesson from stepper-pathly-ui was
implicitly applied (the tester found all locators present).

**Cross-repo coordination was clean.** The PROGRESS.md dependency gate (`Conv 2 may not start
until Conv 1 is committed`) was respected. No ordering violation.

---

## What could have gone better

**The planner agent misidentified the feature type.** The initial plan draft was structured as a
Vitest unit-test plan rather than a Stepper automation plan. The plan files required manual
correction before building could start. This cost one planning cycle.

Root cause: the planner prompt did not explicitly name the feature class ("Stepper automation,
same pattern as stepper-pathly-ui"). Without that anchor, the planner defaulted to the more
common unit-test pattern it had seen.

**The verify_gate blocked a brand-new feature with no build history.** When the feature first
tried to transition from BUILDING to REVIEWING, the FSM `verify_gate` required a `VERIFY.md`
with `RESULT: PASS`. Because this was a new feature with no prior build, no VERIFY.md existed.
The gate fired twice before a pre-created VERIFY.md unblocked it.

Root cause: the gate design assumes a verify step has already been run — it does not distinguish
"never built before" from "built but not verified". New features need either an exemption path
or an explicit pre-creation step in CONVERSATION_PROMPTS.md.

**AC4.2 step-count was written before the wizard step count was finalised.** The story said
"3 clicks" to advance through the wizard; the builder correctly implemented 4 (matching the
actual 5-step wizard). The acceptance criterion was stale. The tester flagged this as FAIL.

Root cause: the story was authored bottom-up from the plan, not from a live read of the
wizard component. Any story that counts interactive steps must be verified against the live
component before writing.

---

## What we'll do differently next time

1. **Name the feature class in the planner prompt.** When the feature is a Stepper automation,
   the planning prompt must say: "This is a Stepper automation feature, same pattern as
   stepper-pathly-ui. Do not generate a unit-test plan." One sentence prevents a planning redo.

2. **Pre-create VERIFY.md for new features.** Add a step to CONVERSATION_PROMPTS.md Conv 1:
   "After the verify command passes, write `RESULT: PASS` to `pathly/plans/<feature>/VERIFY.md`."
   Document this as a required manual step until the pipeline auto-creates it.

3. **Count interactive steps from the live component before writing AC.** Any acceptance
   criterion that references a step count (wizard steps, nav clicks, form fields) must be
   verified against the live component during planning. Add a check to the planner output:
   "For any step-count criterion, read the component source and confirm the count."

4. **Audit touched Studio files against studio/CLAUDE.md rules at the end of every
   Studio-touching conversation.** The reviewer had to catch the missing `type="button"`
   violations — the builder should have caught them. This lesson was already codified from
   stepper-pathly-ui; it needs to be baked into the CONVERSATION_PROMPTS.md preamble for
   all Studio conversations.
