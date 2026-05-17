# studio-ui-fixes — Conversation Prompts

---

## Conversation 1 — Fix event log timestamps and detail (S1)

```
Read pathly/plans/studio-ui-fixes/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Pre-flight: run `cd studio && npm run typecheck` and note any pre-existing errors before touching anything.

You are fixing two visible bugs in the Monitor event log:
1. Events without a `ts` field (e.g. FSM_START) show "Invalid" as the timestamp.
2. STATE_TRANSITION events show an empty detail column because the code reads `ev.detail` but real events have `from`/`to` fields instead.

Work through these phases in order. Do NOT touch Monitor/FsmView.tsx or store/projectStore.ts yet.

Phase 1.1 — types/index.ts
- Make `ts` optional on FsmEvent: `ts?: string`
- Add optional fields: `from?: string`, `to?: string`, `reason?: string`
- Leave all other types unchanged

Phase 1.2 — components/Monitor/index.tsx
- Find both EVENTS.jsonl parsers (initial readFile + onWatchEvent handler)
- Remove `.slice(-50)` from both — it silently drops early events including FSM_START
- No other changes in this file for Conv 1

Phase 1.3 — components/Monitor/EventLog.tsx
- Fix `formatTime`: accept `ts?: string`; return `'—'` if ts is falsy or if `new Date(ts)` produces an invalid date; otherwise return `d.toTimeString().slice(0, 8)`
- Add helper above the component:
  ```ts
  function eventDetail(ev: FsmEvent): string {
    if (ev.from && ev.to) return `${ev.from} → ${ev.to}`
    if (ev.reason) return ev.reason
    return ev.detail ?? ''
  }
  ```
- Replace `{ev.detail}` in the render with `{eventDetail(ev)}`
- Replace `{formatTime(ev.ts)}` call signature to pass the now-optional field (TypeScript will guide you)

Verify: `cd studio && npm run typecheck` → zero errors (subtract any pre-existing baseline).

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with `git checkout` on the affected files and retry.
```

---

## Conversation 2 — Dynamic pipeline states (S2)

```
Read pathly/plans/studio-ui-fixes/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Conv 1 is complete. You are making the Monitor pipeline bar show the actual states from the active flow YAML instead of the hardcoded list ['STORMING','PLANNING','BUILDING','REVIEWING','COMMITTING','DONE'].

Do NOT touch EventLog.tsx, usePlanConversations.ts, Sidebar.tsx, or PlanBoard.tsx in this conversation.

Phase 2.1 — store/projectStore.ts
- Add `pipelineStates: string[]` to ProjectState interface, default to `[]`
- Add `setPipelineStates: (s: string[]) => void` action
- Do NOT add it to the `partialize` list — it is transient, not persisted

Phase 2.2 — components/Monitor/index.tsx
- After the `setFsmState(parsed)` call (when STATE.json loads successfully), attempt to load the flow YAML:
  ```ts
  readFile(`${projectPath}/src/pathly_data/core/flows/${parsed.flow}.flow.yaml`)
    .then((yaml) => {
      const match = yaml.match(/states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/)
      if (match) {
        const states = match[1]
          .trim()
          .split('\n')
          .map((l) => l.replace(/^[ \t]+-[ \t]+/, '').trim())
          .filter(Boolean)
        setPipelineStates(states)
      }
    })
    .catch(() => { /* flow YAML missing — FsmView uses fallback */ })
  ```
- Also call `setPipelineStates([])` in the cleanup / when activeTopic is null
- Add `setPipelineStates` to the `useStore()` destructuring and to the useEffect dependency array

Phase 2.3 — components/Monitor/FsmView.tsx
- Remove the `const PIPELINE: string[] = [...]` constant at the top
- Replace it with:
  ```ts
  const pipelineStates = useStore((s) => s.pipelineStates)
  const PIPELINE = pipelineStates.length > 0
    ? pipelineStates
    : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
  ```
- No other changes — the rest of the component already uses PIPELINE correctly

Verify: `cd studio && npm run typecheck` → zero errors.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with `git checkout` on the affected files and retry.
```

---

## Conversation 3 — PROGRESS parser fix + sidebar debugs/explorations (S3, S4)

```
Read pathly/plans/studio-ui-fixes/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Conv 1 and Conv 2 are complete. This conversation fixes two remaining issues:
- The sidebar PLAN section shows grep commands as status values because the PROGRESS.md parser reads all numeric-row tables
- The sidebar has no DEBUGS or EXPLORATIONS sections even though pathly/debugs/ and pathly/explorations/ exist

Work through these phases in order. Do NOT touch Monitor files or store/projectStore.ts.

Phase 3.1 — types/index.ts
- Add `'debug' | 'explore'` to the PathlyItemType union
- No other changes

Phase 3.2 — hooks/useProjectFiles.ts
- In the SECTIONS constant, add two new entries after Templates:
  ```ts
  { label: 'Debugs',       type: 'debug'    as const, dir: 'pathly/debugs'       },
  { label: 'Explorations', type: 'explore'  as const, dir: 'pathly/explorations' },
  ```
- In INITIAL_SECTIONS, add: `Debugs: { items: [], open: false }`, `Explorations: { items: [], open: false }`
- In the loadItems loop, treat type === 'debug' || type === 'explore' exactly like type === 'template': use listDirs to get subfolders, then listDir per subfolder for files. Keep item type as 'debug' or 'explore' respectively.

Phase 3.3 — components/Sidebar.tsx
- In the SECTIONS array, add the same two entries as Phase 3.2
- In the SECTIONS.map render, add `|| section.type === 'debug' || section.type === 'explore'` to the condition that checks `section.type === 'template'`
- No other changes — the subdir rendering branch already handles the UI correctly

Phase 3.4 — hooks/usePlanConversations.ts
Replace parseProgressMd with a version that scopes to the Conversation Breakdown table only:
```ts
function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  const lines = md.split('\n')
  let inSection = false
  let headerParsed = false
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('## Conversation Breakdown')) { inSection = true; continue }
    if (inSection && trimmed.startsWith('##')) break
    if (!inSection) continue
    if (!trimmed.startsWith('|')) continue
    const parts = trimmed.split('|').map((p) => p.trim()).filter(Boolean)
    if (!headerParsed) { headerParsed = true; continue }
    if (parts[0]?.startsWith('---')) continue
    const num = parseInt(parts[0], 10)
    if (isNaN(num)) continue
    // columns: Conv, Phases(title), Stories, Status — NOT the last Verify column
    const status = parts[3] ?? ''
    rows.push({ num, title: parts[1] ?? '', status: status.toUpperCase() })
  }
  return rows
}
```

Phase 3.5 — components/PlanBoard.tsx
- Apply the same parseProgressMd fix (same logic as Phase 3.4)
- Remove the per-conversation event filtering: `events.filter(e => e.conversation === conv.num)` — real events have no conversation field
- Instead, add a "Recent events" section below the conversation cards that renders all events from EVENTS.jsonl flat (same rendering style as EventLog)
- Keep the conversation cards themselves — they correctly show status from PROGRESS.md

Verify: `cd studio && npm run typecheck` → zero errors.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with `git checkout` on the affected files and retry.
```
