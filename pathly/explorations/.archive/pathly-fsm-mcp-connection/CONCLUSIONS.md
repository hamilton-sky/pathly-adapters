# CONCLUSIONS — pathly-fsm-mcp-connection

## Answer

**The implementation is complete** — `mcp_server.py` exists, tools are registered, `fsm.py` imports cleanly, and the `pyproject.toml` entry point is correct. The tools aren't appearing because **the server is crashing silently at startup and we don't yet know why.** Claude Code drops MCP servers that fail to start without surfacing the error to the user.

## What we know

| Item | Status |
|------|--------|
| `pathly-fsm.exe` exists at registered path | ✅ |
| `mcp_server.py` imports cleanly | ✅ |
| `next_action` + `complete_stage` registered in `_TOOLS` | ✅ |
| `pyproject.toml` entry point correct | ✅ |
| All PROGRESS.md convs marked DONE | ✅ |
| `settings.json` matches `mcp_config.py` output | ❌ — settings uses `.exe`, mcp_config.py generates `python -m` |
| `human.md` agent file exists | ❌ — missing, all flows reference it |

## Confirmed bugs

### Bug 1 — Missing `human.md` (runtime crash, not startup)
All three flow YAMLs (`team`, `debug`, `explore`) declare `human` as a `feedback_routing` target. `mcp_server.py:_load_agent_text("human")` at line 113 will raise `FileNotFoundError` when any flow routes feedback to a human. This is a runtime crash, not a startup failure.

**Fix:** Create `src/pathly_data/core/agents/human.md` with a stub that explains the human-blocked protocol.

### Bug 2 — Settings.json not written by current mcp_config.py
`settings.json` has the `.exe` form; `mcp_config.py` generates the `python -m` form. This means `pathly-setup install` (or equivalent) was not re-run after mcp_config.py was finalized.

Both forms invoke the same `main()` so this alone is not the failure. But it means the install step is incomplete.

**Fix:** Run `pathly-setup install` (or call `mcp_config.apply_claude()`) to regenerate the settings.json entry to the canonical form.

## Unresolved — needs a live test

We cannot confirm **why** the exe crashes without running it and capturing stderr. The implementation looks correct on paper, but something is failing during the MCP handshake or stdio framing.

**Recommended next step:**

```powershell
# Run the server directly and observe what it outputs / crashes on
& "C:\Users\Yafit\AppData\Local\Programs\Python\Python313\Scripts\pathly-fsm.exe" 2>&1
# or
python -m pathly_orchestrator.mcp_server 2>&1
```

If it hangs waiting for stdin (correct MCP behavior), send a `tools/list` request manually:

```
Content-Length: 57\r\n\r\n{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

## Recommendation

1. **Run the exe manually** to capture the crash / startup output — this will identify the actual failure in minutes.
2. **Create `human.md`** to fix the confirmed runtime crash.
3. **Re-run `pathly-setup install`** to sync settings.json with mcp_config.py.
4. If the server starts cleanly after step 1, restart Claude Code and verify tools appear.

## Confidence

- Missing `human.md` bug: **high confidence** (all scouts agree, file clearly absent)
- Settings.json discrepancy: **high confidence** (Scout 2 cited exact lines)
- Root cause of session-start failure: **unknown** — needs live test
