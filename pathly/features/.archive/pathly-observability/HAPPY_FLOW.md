# Happy Flow — pathly-observability

This walkthrough shows the end-to-end experience once all four conversations are complete.

---

## 1. Builder starts a build session

The builder agent begins work on a feature. At the top of the analyze phase, `build.md` instructs:

```
log-phase PHASE_START analyze
```

This calls:
```bash
curl -s -X POST http://127.0.0.1:8765/record_phase \
  -H "Content-Type: application/json" \
  -d '{"feature":"my-feature","agent":"builder","phase":"analyze","event_type":"PHASE_START","conv":1}'
```

Response: `{"status": "recorded"}`

`pathly/plans/my-feature/EVENTS.jsonl` now contains:
```json
{"schema_version":1,"type":"PHASE_START","phase":"analyze","agent":"builder","feature":"my-feature","conv":1,"ts":"2026-06-02T10:00:00Z"}
```

---

## 2. Builder finishes analyze, enters scout phase

At the phase boundary, `build.md` calls:
```
log-phase PHASE_DONE analyze
log-phase PHASE_START scout
```

Two more lines are appended to EVENTS.jsonl.

---

## 3. Builder spawns scouts, records count

After 2 scouts return, `build.md` calls:
```
log-phase PHASE_DONE scout scouts_count=2
```

EVENTS.jsonl receives:
```json
{"schema_version":1,"type":"PHASE_DONE","phase":"scout","agent":"builder","feature":"my-feature","conv":1,"scouts_count":2,"ts":"2026-06-02T10:03:00Z"}
```

---

## 4. Builder implements and finishes

```
log-phase PHASE_START implement
... code edits happen ...
log-phase PHASE_DONE implement total_tokens=8200 tool_uses=12
```

EVENTS.jsonl now has 6 PHASE_* events for this conversation, plus the existing AGENT_DONE at the end.

---

## 5. Reviewer runs

`review.md` similarly logs PHASE_START/DONE for its analyze, scout, and review phases. The
operator can now query EVENTS.jsonl and see the full phase timeline:

```
PHASE_START analyze  (builder, conv 1)
PHASE_DONE  analyze  (builder, conv 1)
PHASE_START scout    (builder, conv 1)
PHASE_DONE  scout    (builder, conv 1, scouts_count=2)
PHASE_START implement(builder, conv 1)
PHASE_DONE  implement(builder, conv 1, total_tokens=8200)
AGENT_DONE           (builder, conv 1)
PHASE_START analyze  (reviewer, conv 2)
PHASE_DONE  analyze  (reviewer, conv 2)
...
```

---

## 6. Pipeline operator checks rigor compliance

The operator reads the builder's agent contract and sees the rigor_contract table:

| Rigor | Scout limit | Verify gate | Scope gate |
|---|---|---|---|
| standard | up to 4 scouts | tests pass | scope_gate active |

The EVENTS.jsonl shows `scouts_count=2` for standard rigor — within budget. The stage_brief
in builder.md confirms `Done when: python -m pytest tests/ -q exits 0`. The operator can
confirm compliance from artifacts alone without reading conversation transcripts.

---

## 7. New adapter path added without Python edit

A developer wants to exempt `~/.antigravity/agents/` from scope gate checks. They add:

```yaml
scope_gate:
  exempt_prefixes:
    - ".antigravity/agents/"
```

to the active flow YAML. On next FSM load, `_is_exempt()` recognizes the new prefix. No Python
source change required.

---

## End state

- EVENTS.jsonl contains a structured timeline of PHASE_START, PHASE_DONE, and AGENT_DONE events
- Every build, review, test, plan, design, and storm session appends phase events automatically
- Agent contracts are self-documenting on rigor requirements
- Adapter install propagates updated agent contracts to ~/.claude/ and ~/.codex/
