# Exploration — architecture-risk-assessment

## Question
Are the 5 identified real risks actual vulnerabilities in the current codebase, how severe is each,
and what is the minimal fix or contract change needed to close each one?

## Risks under investigation
1. **Hooks silent failure** — PATHLY_PROJECT_ROOT missing → hooks are silent no-ops; no diagnostic log; no documented contract
2. **Codex unverified on clean machine** — adapter committed, setup runs clean, but no end-to-end smoke test on a fresh machine
3. **pathly_orchestrator dual role** — internal FSM schema + public CLI (`pathly-events`, `pathly-state`) — event schema changes break user state; no migration story
4. **Version drift** — docs can lag pyproject.toml version; no CI gate enforcing sync
5. **http_config.py opaque** — module purpose not documented in README or module table

## Scope
- `src/pathly_hooks/classify_feedback.py`
- `src/pathly_hooks/inject_feedback_ttl.py`
- `src/install_cli/materialize.py` (hook deployment)
- `src/install_cli/codex_plugin_config.py`
- `src/install_cli/http_config.py`
- `src/pathly_orchestrator/events.py`, `eventlog.py`, `state.py`, `__init__.py`
- `pyproject.toml` (version + entry points)
- `tests/test_codex_plugin_config.py`, `tests/test_hooks.py`
- README / docs for version string and module table
- `.github/` or CI config for version-gate checks

## Out of scope
- Telemetry server internals (`pathly_telemetry`)
- Skill/agent prompt content
- Pipeline walkthrough artifacts

## Success criterion
For each of the 5 risks: (a) confirm it is real or a false alarm, (b) rate severity
(critical / moderate / low), (c) identify the exact file:line that is the root cause,
(d) state the minimal fix.
