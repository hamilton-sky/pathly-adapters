# log-phase

Internal utility — logs a phase boundary event to EVENTS.jsonl via the HTTP server.
Call this at the entry and exit of each named phase within a skill workflow.

Phase logging is best-effort. If the HTTP server is not running, the call fails silently
and must never block skill execution.

## Purpose

Record PHASE_START and PHASE_DONE events so the pipeline walkthrough has fine-grained
timing and structure information per agent phase.

## Usage syntax

```
log-phase <event_type> <phase> [optional args]
```

- `event_type`: `PHASE_START` or `PHASE_DONE`
- `phase`: `analyze`, `scout`, `implement`, `review`, `test`, `plan`, or any named phase
- Optional args are passed as additional JSON fields (see below)

## Curl command

```bash
curl -s -X POST http://127.0.0.1:8765/record_phase \
  -H "Content-Type: application/json" \
  -d '{"feature":"<FEATURE>","agent":"<AGENT>","phase":"<PHASE>","event_type":"<EVENT_TYPE>"}'
```

Replace `<FEATURE>` with the feature slug (from the active plan folder), `<AGENT>` with the
current agent role (e.g. `builder`, `reviewer`, `tester`, `planner`), `<PHASE>` with the
phase name, and `<EVENT_TYPE>` with `PHASE_START` or `PHASE_DONE`.

## Optional fields

Include any of these as additional JSON fields in the `-d` body when available:

- `conv` (integer): current conversation number
- `scouts_count` (integer): number of scout agents spawned (relevant on PHASE_DONE scout)
- `total_tokens` (integer): token count from the phase's sub-agent response
- `tool_uses` (integer): tool call count from the phase's sub-agent response

Example with optional fields:

```bash
curl -s -X POST http://127.0.0.1:8765/record_phase \
  -H "Content-Type: application/json" \
  -d '{"feature":"my-feature","agent":"builder","phase":"scout","event_type":"PHASE_DONE","conv":2,"scouts_count":3}'
```

## Silent failure

If the HTTP server is not running, the curl command will fail silently (due to `-s` flag and
no error handling). This is the intended behavior — phase logging must never block or fail
skill execution.
