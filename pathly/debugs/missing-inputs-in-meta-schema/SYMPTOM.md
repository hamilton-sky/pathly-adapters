# Symptom — missing-inputs-in-meta-schema

## What broke
`orchestrator.yaml` (and potentially other agent meta YAML files) declare an `inputs` block, but `pathly-meta.schema.json` has no `inputs` property defined.

## How it manifests
Schema validation against `pathly-meta.schema.json` would reject any meta YAML file containing an `inputs` key, because the schema enforces `"additionalProperties": false` and `inputs` is not listed as an allowed property.

Example: `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` defines:
```yaml
inputs:
  flow_config:
    description: "Path to a *.flow.yaml file defining the FSM for this run"
    required: true
  topic:
    description: "Feature name, symptom name, or exploration topic — substituted into storage_path"
    required: true
```
This block would be rejected by the schema.

## Environment
- Branch: master
- File: `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` (lines 6-13)
- Schema: `src/pathly_data/schemas/pathly-meta.schema.json` (no `inputs` property, `additionalProperties: false`)

## Expected behavior
`pathly-meta.schema.json` should define an `inputs` property that describes the structure of agent input parameter declarations, so YAML files using `inputs` pass schema validation.
