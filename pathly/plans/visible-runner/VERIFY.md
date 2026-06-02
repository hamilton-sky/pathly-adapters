RESULT: PASS

Conv 2 review passed. 3 violations from round 1 all resolved.

## Violations resolved

1. StageLogEntry.mode field added to runnerStore.ts (line 16: `mode: 'terminal' | 'headless' | null`)
2. attachTerminalToStage() action added to runnerStore - correctly patches last stageLog entry with tabId + mode, updates activeRunnerTabId
3. useHQ.tsx SSE handler ordering fixed:
   - STAGE_CHANGE now calls recordStageStart (with reconnect guard checking endedAt===null and matching stage name)
   - TERMINAL_SPAWN now calls attachTerminalToStage(tab_id, 'terminal') instead of recordStageStart
   - TERMINAL_SIGNAL now uses data.tab_id first, falls back to activeRunnerTabId

## Other checks - all pass

- TypeScript: both tsconfig.web.json and tsconfig.node.json check clean (0 errors)
- No inline styles in any changed component
- All buttons have explicit type="button"
- CSS tokens (--runner-bg, --runner-border, --runner-bg-hover) defined in tokens.css for all themes
- tabRunner CSS class in Terminal.module.css uses var(--runner-bg) / var(--runner-border) correctly
- runnerOwned field on TerminalTab used for tab styling (no string-prefix sniffing)
- State ownership boundaries match architecture: PTY output in Electron main, stageLog in renderer
- terminal.ts: fire-and-forget POST to /runner/terminal/result with one retry on error
- Dead code: `const stage` in TERMINAL_SPAWN handler (line 265) is unused after the fix but does not cause a TS error (noUnusedLocals not set); minor smell only, not a violation
