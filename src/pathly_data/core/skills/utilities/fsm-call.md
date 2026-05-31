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

```bash
curl -s --max-time 1 http://127.0.0.1:8765/health
```

If it returns `{"status":"ok"}`, proceed to Step 3.

If it fails or times out:
1. Start the server in the background:
   ```bash
   python -m pathly_orchestrator.http_server &
   ```
2. Wait 2 seconds, then retry the health check once.
3. If still unavailable:
   ```
   FSM server unavailable. Start it with:
     python -m pathly_orchestrator.http_server
   (Run in a separate terminal, then retry.)
   ```
   Stop.

## Step 3 - POST to endpoint

Prefer the helper CLI:

```bash
pathly-fsm-call next-action \
  --flow "<flow>" \
  --topic "<topic>" \
  --project-root "<project_root>"
```

Use `pathly-fsm-call complete-stage` for stage advancement and
`pathly-fsm-call record-activity` for telemetry. Omit `--decision` and
`--resolved-file` unless needed.

If the helper is unavailable, fall back to direct HTTP.

Build the JSON body from the parsed fields (omit `decision` and `resolved_files` if not provided):

```bash
curl -s -X POST http://127.0.0.1:8765/<action> \
  -H "Content-Type: application/json" \
  -d '<body>'
```

## Step 4 - Return response

Print the raw JSON response exactly as received. The calling skill parses and acts on it.

If the call fails or returns a non-200 status, print:
```
fsm-call error (<status>): <response body>
```
and stop.
