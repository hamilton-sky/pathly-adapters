# AI-Assisted Flow Wizard - User Stories

## S1: The wizard can represent shipped Pathly flows

**As a** Studio user, **I want** the Flow Wizard to edit the same schema the runtime already consumes, **so that** creating or reopening a flow does not discard behavior.

**Acceptance criteria**
- The wizard reads and writes `version`, `flow`, `storage_path`, `states`, `transitions`, `agent_map`, `role_map`, `feedback_routing`, `transition_rules`, `transition_actions`, and `gates`.
- Loading and saving a representative shipped flow preserves all supported behavior keys.
- YAML output is produced through structured serialization, not manual string construction.
- The existing `description` control is either removed from saved-flow editing or clearly presented as AI draft intent only; user-entered data is not silently discarded.

## S2: The wizard validates a full flow before saving

**As a** Studio user, **I want** invalid drafts rejected with useful messages, **so that** the runtime does not receive broken state graphs or actions.

**Acceptance criteria**
- State, transition, rule target, feedback role, gate, and transition-action references are validated before save.
- Duplicate or empty states and missing required fields are surfaced in the wizard.
- Existing FlowEditor validation logic is reused or extended instead of duplicated with inconsistent rules.
- A draft with validation errors cannot be saved without correction.

## S3: The LLM creates a structured draft inside the wizard

**As a** user defining a workflow, **I want** to describe my goal in natural language, **so that** the wizard begins with an editable full-schema draft.

**Acceptance criteria**
- The Flow Wizard contains an AI drafting entry point and natural-language input.
- The LLM is prompted to return a constrained full flow document matching the canonical schema.
- Valid model output populates wizard state; it does not auto-save or execute anything.
- The user can edit all generated schema areas before saving.
- Both supported local-model routes use the existing LLM bridge after its typing contract is repaired.

## S4: Model failure is recoverable and does not destroy user work

**As a** user, **I want** failed generation to leave my current flow intact, **so that** trying AI assistance is safe.

**Acceptance criteria**
- Invalid YAML/JSON, partial model responses, bridge errors, and aborted requests display an error while retaining the prior wizard state.
- A generated draft is parsed and validated before replacing editable fields.
- A new request cannot silently save or overwrite a file.

## S5: The user understands what the AI changed

**As a** user reviewing a generated flow, **I want** clear draft/validation status, **so that** I can approve the design deliberately.

**Acceptance criteria**
- AI output is labeled as a draft until saved.
- Validation issues are visible before Save is enabled.
- The review step shows the canonical YAML that will be written.
- Existing manually-authored flows remain editable without invoking AI.

## Non-goals

- The LLM does not click wizard controls through Playwright.
- The LLM does not run `storm`, `build`, or any Pathly phase from this wizard feature.
- Locator cascade resolution and self-healing are not required for creating internal Studio flow definitions.
