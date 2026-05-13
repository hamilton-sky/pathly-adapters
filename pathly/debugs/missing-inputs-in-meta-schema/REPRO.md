# Repro — missing-inputs-in-meta-schema

## Repro Status
[CONFIRMED] — any JSON Schema validator running `pathly-meta.schema.json` against a meta YAML with `inputs` will reject it due to `additionalProperties: false`

## Steps
1. Load any `_meta/*.yaml` file that contains an `inputs` block via `yaml.safe_load()`
2. Run `jsonschema.validate(data, pathly_meta_schema)` against `src/pathly_data/schemas/pathly-meta.schema.json`
3. Observe `ValidationError: Additional properties are not allowed ('inputs' was unexpected)`

## Files involved
- `src/pathly_data/schemas/pathly-meta.schema.json:115` — `"additionalProperties": false` with no `inputs` property defined
- `src/pathly_data/adapters/claude/_meta/orchestrator.yaml:6-13` — defines `inputs` block
- `src/pathly_data/adapters/codex/_meta/orchestrator.yaml:5-11` — also defines `inputs` block

## All YAML files with `inputs`
- `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` lines 6-13
- `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` lines 5-11

## `inputs` entry structure
Each value under `inputs` is an object with:
- `description` (string) — human-readable description of the parameter
- `required` (boolean) — whether the input is mandatory

## Hypothesis
The `inputs` property was added to agent meta YAML files but never backfilled into the schema, causing schema validation to reject any YAML that declares agent inputs.
