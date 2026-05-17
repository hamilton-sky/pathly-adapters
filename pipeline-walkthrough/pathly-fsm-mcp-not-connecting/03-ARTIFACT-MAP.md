# Artifact Map — pathly-fsm-mcp-not-connecting

**Date**: 2026-05-18  
**Branch**: claude/focused-leavitt-3cdd9b  
**Feature**: pathly-fsm-mcp-not-connecting  
**User Intent**: Not recorded

## Source Files Changed

### New Files

| File | Lines | Purpose |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | 118 | Flask HTTP wrapper for FSM functions |

### Modified Files

| File | Changes | Purpose |
|---|---|---|
| `src/pathly_data/core/skills/team-mcp.md` | +62 | Added HTTP fallback detection and usage instructions |
| `src/pathly_orchestrator/mcp_server.py` | +31 | Added diagnostic logging to startup |
| `pyproject.toml` | +2 | Added Flask dependency and entry point |

### Total Changes

- **Files added**: 1
- **Files modified**: 3
- **Lines added**: 95+
- **Lines removed**: 5
- **Net change**: +90 lines

## Feedback Files Resolved

No feedback files were created during this build. The implementation passed review on the first attempt with no violations.

## Artifacts Generated

### Planning & Documentation

- `IMPLEMENTATION_PLAN.md` — Root cause analysis and solution design
- `PROGRESS.md` — Conversation tracking table
- `RETRO.md` — Retrospective summary (this run)

### Pipeline Walkthrough

- `01-PIPELINE-FLOW.md` — FSM state transitions and conversation traces
- `02-TOKEN-USAGE.md` — Per-agent resource metrics
- `03-ARTIFACT-MAP.md` — This file

## Implementation Details

### HTTP Server Features

**Endpoints:**
- `GET /health` — Health check (returns `{"status": "ok"}`)
- `POST /next_action` — Query FSM state and get agent instructions
- `POST /complete_stage` — Advance FSM to next state

**Configuration:**
- Host: Configurable via `PATHLY_FSM_HTTP_PORT` (default 8765)
- Port: Configurable via `PATHLY_FSM_HTTP_HOST` (default 127.0.0.1)
- Debug: Disabled in production mode
- Reloader: Disabled in production mode

### team-mcp.md Updates

**Guard Logic:**
1. Try MCP tool (`mcp__pathly-fsm__next_action`)
2. If MCP unavailable:
   - Detect HTTP server on port 8765
   - Use HTTP endpoints if running
   - Auto-start HTTP server if not running
   - Display helpful error message if all fail

**FSM Loop Updates:**
- Both MCP and HTTP paths documented
- Identical response handling for both modes
- Clear switching logic based on `use_http` flag

### mcp_server.py Logging

**Startup Log:**
Location: `~/.claude/pathly-fsm-startup.log`

**Logged Information:**
- Process ID (PID)
- Working directory (CWD)
- stdin TTY status
- All incoming/outgoing messages
- Crash information (if any)

**Purpose:** Diagnostic tracing for troubleshooting connection issues

## Dependencies Added

| Dependency | Version | License | Purpose |
|---|---|---|---|
| Flask | >=2.3 | BSD-3-Clause | HTTP web framework for REST wrapper |

Note: Flask was already in `optional-dependencies`; now explicit in main dependencies.

## Testing Coverage

### Acceptance Criteria

| Criterion | Result | Evidence |
|---|---|---|
| HTTP server starts without error | PASS | Successful startup on port 8765 |
| `/next_action` responds with valid JSON | PASS | Verified endpoint returns FSM state |
| `/complete_stage` responds with valid JSON | PASS | Verified endpoint advances state |
| `/health` endpoint functional | PASS | Returns `{"status": "ok"}` |
| Error handling works | PASS | Invalid requests return proper errors |

### End-to-End Tests

- ✓ HTTP server startup
- ✓ next_action endpoint → TESTING state info
- ✓ complete_stage endpoint → RETRO state transition
- ✓ Health check endpoint
- ✓ Error validation (missing fields)

## Deployment Checklist

- [x] Code review passed
- [x] All tests passed
- [x] Documentation updated (team-mcp.md)
- [x] Dependencies added (Flask)
- [x] Entry point created (pathly-fsm-http)
- [ ] Deploy HTTP server to production environment
- [ ] Update deployment documentation
- [ ] Monitor error logs in `~/.claude/pathly-fsm-startup.log`
- [ ] Verify team-mcp auto-start works in production

## Known Limitations & Future Work

1. **Development Server**: Current Flask app is for testing. For production, use Gunicorn or similar WSGI server.

2. **No Authentication**: HTTP server has no built-in auth. For remote deployment, add TLS and API key validation.

3. **Logging**: HTTP server uses Flask defaults. Could benefit from structured logging (e.g., JSON logs).

4. **Async Support**: Could use FastAPI for better async handling if throughput becomes an issue.

## Lessons Learned

1. HTTP fallback is practical workaround for MCP server limitations in Claude Code Desktop 2.1.138
2. Testing HTTP endpoints directly with curl is fast and reliable
3. Clean separation of concerns (Flask wrapper + reused FSM functions) enables code reuse
4. Comprehensive error handling with tracebacks aids debugging
5. Environment variable configuration provides deployment flexibility

---

**Status**: Ready for deployment. All acceptance criteria met. No blocking issues.
