# AI-Assisted Flow Wizard - Happy Flow

## Scenario

A user wants a Pathly feature-delivery flow with planning, implementation, review feedback, and testing.

1. The user opens **New Flow** in Studio.
2. In the Flow Wizard, the user enters an intent such as: `Create a feature workflow with planning, building, review feedback back to build, testing failures back to build, and completion.`
3. The user clicks **Generate Draft**.
4. The LLM returns a structured draft using the canonical flow schema.
5. Studio parses and validates the response before changing the form.
6. The wizard fields populate with states, transitions, agent and role mappings, feedback routing, transition rules, transition actions, gates, and storage path.
7. The user reviews or edits the generated fields.
8. The review step displays the canonical YAML that will be saved and any remaining validation issues.
9. Once valid, the user saves the flow.
10. The saved `.flow.yaml` opens in the visual editor without losing schema fields.

## End state

The user created a runtime-compatible Pathly flow through guided natural language plus explicit human review. No Playwright interaction, phase execution, or self-healing is involved in creating the definition.

## Success indicators

- A shipped full-schema flow can round-trip through the wizard.
- AI generation populates editable wizard state rather than executing actions.
- Validation blocks invalid graphs before save.
- Manual wizard creation still works when AI is not used.
