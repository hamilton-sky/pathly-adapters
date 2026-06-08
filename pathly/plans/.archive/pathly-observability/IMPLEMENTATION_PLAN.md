# Implementation Plan — pathly-observability

## Scope summary

Four conversations deliver structured phase-level observability across the Pathly stack:
- New `/record_phase` HTTP endpoint + event schema (Python layer)
- Phase-boundary `log-phase` calls in all six development skills (skill layer)
- Explicit analyze phase in design.md and storm.md (skill layer)
- `rigor_contract` + `stage_brief` sections in all six agent contracts (agent layer)
- Adapter propagation to claude and codex adapters

---

## Canonical event schema (CANDIDATE-007)

All new events written to `pathly/plans/<feature>/EVENTS.jsonl` must conform to these schemas.
Builders must embed these exactly — do not invent additional fields.

### PHASE_START

```json
{
  "schema_version": 1,
  "type": "PHASE_START",
  "phase": "<analyze|scout|implement|review|test|plan|design|storm>",
  "agent": "<builder|reviewer|tester|planner|architect|designer>",
  "feature": "<feature-slug>",
  "conv": 1,
  "ts": "2026-06-02T10:00:00Z"
}
```

Required fields: `schema_version`, `type`, `phase`, `agent`, `feature`, `ts`
Optional fields: `conv`

### PHASE_DONE

```json
{
  "schema_version": 1,
  "type": "PHASE_DONE",
  "phase": "<analyze|scout|implement|review|test|plan|design|storm>",
  "agent": "<builder|reviewer|tester|planner|architect|designer>",
  "feature": "<feature-slug>",
  "conv": 1,
  "total_tokens": 12500,
  "tool_uses": 14,
  "scouts_count": 2,
  "ts": "2026-06-02T10:05:00Z"
}
```

Required fields: `schema_version`, `type`, `phase`, `agent`, `feature`, `ts`
Optional fields: `conv`, `total_tokens`, `tool_uses`, `scouts_count`

### Allowed `phase` values

`analyze` | `scout` | `implement` | `review` | `test` | `plan` | `design` | `storm`

### Allowed `event_type` values for `/record_phase`

`PHASE_START` | `PHASE_DONE`

---

## `/record_phase` endpoint spec

```
POST /record_phase
Content-Type: application/json

Request body:
  feature      str   REQUIRED — feature slug (used to locate EVENTS.jsonl)
  agent        str   REQUIRED — agent role name
  phase        str   REQUIRED — must be in allowed phase enum
  event_type   str   REQUIRED — "PHASE_START" or "PHASE_DONE"
  conv         int   optional
  total_tokens int   optional (PHASE_DONE only, ignored on PHASE_START)
  tool_uses    int   optional (PHASE_DONE only)
  scouts_count int   optional (PHASE_DONE only)
  summary      str   optional

Response (success):
  HTTP 200
  {"status": "recorded"}

Response (validation error):
  HTTP 400
  {"error": "<description>"}

Side effect:
  Appends one JSON line to pathly/plans/<feature>/EVENTS.jsonl
  Creates the file if it does not exist
  Does NOT create the plans/<feature>/ directory — caller must ensure it exists
```

---

## Rigor contract tables (embed in agents — S-08)

### Builder

| Rigor | Scout limit | Verify gate | Scope gate |
|---|---|---|---|
| nano | no scouts | none | none |
| lite | 1 scout allowed | typecheck only | none |
| standard | up to 4 scouts | tests pass | scope_gate active |
| strict | up to 4 scouts + wide required | tests + review pass | scope_gate + audit |

### Reviewer

| Rigor | Input | Scope | Extra |
|---|---|---|---|
| nano | skip review entirely | — | — |
| lite | diff + rules check | — | — |
| standard | diff + rules + scope gate | active | — |
| strict | standard + security check | active | REVIEW_FAILURES.md required |

### Tester

| Rigor | Coverage | Edge cases | Regression |
|---|---|---|---|
| nano | smoke only (1 path) | none | none |
| lite | happy path | none | none |
| standard | happy path + edge cases | per EDGE_CASES.md | none |
| strict | standard + regression suite | full | TEST_FAILURES.md required |

### Planner

| Rigor | Scouts | PO session | Stories |
|---|---|---|---|
| nano | skip consult | not required | 1–2 stories |
| lite | 1 scout | not required | 2–4 stories |
| standard | full consult + up to 4 scouts | optional | full story set |
| strict | full consult + up to 4 scouts | required | full set + PO sign-off |

### Architect

| Rigor | Research | Web | Output |
|---|---|---|---|
| nano | direct answer, no scouts | none | inline answer |
| lite | 1 scout | none | DESIGN_SPEC.md draft |
| standard | up to 4 scouts | optional | DESIGN_SPEC.md full |
| strict | up to 4 scouts | web-researcher required | DESIGN_SPEC.md + ARCH_REVIEW.md |

### Designer

| Rigor | Phase 1 (analyze) | Scouts | Audit |
|---|---|---|---|
| nano | skip | none | none |
| lite | 1 scout | 1 scout | none |
| standard | full 3-phase | up to 4 scouts | — |
| strict | full 3-phase | up to 4 scouts | DESIGN_REVIEW.md required |

---

## Conversation breakdown

### Conv 1 — Python infrastructure

Stories: S-01, S-02, S-03
Files touched:
- `src/pathly_orchestrator/http_server.py`
- `src/pathly_orchestrator/fsm.py`
- One flow YAML file in `src/pathly_data/core/flows/` (builder must glob to find the right one)
- `tests/` — add tests for `/record_phase` endpoint

Done when: `python -m pytest tests/ -q` passes with new endpoint tests included.

### Conv 2 — Skill phase logging

Stories: S-04, S-05, S-06
Files touched:
- `src/pathly_data/core/skills/development/build.md`
- `src/pathly_data/core/skills/development/review.md`
- `src/pathly_data/core/skills/development/test.md`
- `src/pathly_data/core/skills/development/plan.md`
- `src/pathly_data/core/skills/utilities/log-phase.md` (new file)

Done when: `grep -r "log-phase\|PHASE_START" src/pathly_data/core/skills/development/` returns at least 10 matches across the four skill files.

Gate: Conv 1 Python tests must pass before starting Conv 2.

### Conv 3 — design.md + storm.md phases

Stories: S-07
Files touched:
- `src/pathly_data/core/skills/development/design.md`
- `src/pathly_data/core/skills/development/storm.md`

Done when: `grep -n "phase: analyze" src/pathly_data/core/skills/development/design.md src/pathly_data/core/skills/development/storm.md` returns at least 2 matches (one per file).

### Conv 4 — Agent contracts + adapter propagation

Stories: S-08, S-09
Files touched:
- `src/pathly_data/core/agents/building/builder.md`
- `src/pathly_data/core/agents/quality/reviewer.md`
- `src/pathly_data/core/agents/quality/tester.md`
- `src/pathly_data/core/agents/planning/planner.md`
- `src/pathly_data/core/agents/planning/architect.md`
- `src/pathly_data/core/agents/building/designer.md`

Done when:
1. `grep -r "Rigor contract" src/pathly_data/core/agents/` returns 6 matches
2. `grep -r "Stage brief" src/pathly_data/core/agents/` returns 6 matches
3. `pathly-setup claude --apply` exits 0
4. `pathly-setup codex --apply` exits 0

---

## Files NOT touched

- `src/pathly_orchestrator/supervisor.py` — no phase tracking needed at the supervisor level in this feature
- `src/pathly_orchestrator/runner.py` — runner does not write EVENTS.jsonl directly
- `studio/` — no frontend changes in this feature
- Antigravity or copilot adapters — neither has a `_meta/` directory yet; excluded from adapter propagation
