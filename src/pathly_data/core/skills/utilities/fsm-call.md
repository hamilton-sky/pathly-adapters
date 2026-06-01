# fsm-call

Internal utility - makes a single HTTP call to the Pathly FSM server.
The packaged `pathly-fsm-call` helper is the canonical Codex-friendly bridge;
all other skills delegate FSM calls here instead of duplicating transport logic.
It ensures the server is running first, auto-starting it if needed.

## Arguments

`$ARGUMENTS` is a JSON object string with these fields:
- `action` (required): `"next_action"` or `"complete_stage"`
- `flow` (required): flow name, e.g. `"team"`
- `topic` (required): feature slug
- `project_root` (required): absolute path to the project directory
- `decision` (optional): decision key for `complete_stage` routing decisions
- `resolved_files` (optional): array of feedback filenames to mark resolved

## Step 1 - Parse arguments

Parse `$ARGUMENTS` as JSON. If any required field is missing, print:
```
fsm-call: missing required field(s): <list>. Pass a JSON object with action, flow, topic, project_root.
```
and stop.

## Step 2 - Ensure server is running

Call `pathly-fsm-call <subcommand> ...` - the helper handles health-check,
auto-start, and retry automatically.

## Step 3 - POST to endpoint

Use the helper CLI as the canonical transport:

```bash
pathly-fsm-call next-action \
  --flow "<flow>" \
  --topic "<topic>" \
  --project-root "<project_root>"
```

Use `pathly-fsm-call complete-stage` for stage advancement and
`pathly-fsm-call record-activity` for telemetry. Omit `--decision` and
`--resolved-file` unless needed.

If the helper is unavailable, fall back to direct HTTP only in a debug
session, and use a real JSON encoder rather than hand-built shell escaping.
Do not rely on raw `curl` examples as the primary contract.

## Step 4 - Return response

Print the raw JSON response exactly as received. The calling skill parses and acts on it.

If the call fails or returns a non-200 status, print:
```
fsm-call error (<status>): <response body>
```
and stop.
