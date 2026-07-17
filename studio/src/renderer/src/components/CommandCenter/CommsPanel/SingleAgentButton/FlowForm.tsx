import { useState, useEffect, useMemo } from 'react'
import { Play } from 'lucide-react'
import { PATHLY_API_BASE } from '../../../../lib/config'
import { BOARD_FLOWS } from './flowCatalog'
import { FlowDiagram } from './FlowDiagram/FlowDiagram'
import { FlowAbout } from './FlowAbout/FlowAbout'
import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import s from './SingleAgentButton.module.css'

interface Props {
  /** Board key: a feature id, or 'project'. Scopes which flows are offered + how they run. */
  boardKey: string
  running: boolean
  onRunFlow: (flow: string, opts: { interactive: boolean }) => void
  onClose: () => void
}

const KNOWN = new Map(BOARD_FLOWS.map((f) => [f.key, f]))

// Flow mode of the run modal: pick ANY Pathly flow (fetched live from GET /flows, so
// consultation + user-created flows appear — not just the 5 hardcoded ones), preview it, then run
// the whole flow on this board's topic. Known flows get the rich diagram + About; others show a
// terse note. Falls back to the hardcoded catalog if the server is unreachable.
// Cached so switching to the Flow tab (which re-mounts this form) doesn't re-fetch and flicker.
let _flowsCache: string[] | null = null

export function FlowForm({ boardKey, running, onRunFlow, onClose }: Props): JSX.Element {
  const [serverNames, setServerNames] = useState<string[]>(_flowsCache ?? [])
  const [flowKey, setFlowKey] = useState<string>('')
  const [interactive, setInteractive] = useState(true)

  useEffect(() => {
    if (_flowsCache) return
    let cancelled = false
    void (async () => {
      try {
        const r = await fetch(`${PATHLY_API_BASE}/flows`)
        const data = r.ok ? await r.json() : []
        if (Array.isArray(data)) {
          const names = data.map((f: { name?: string }) => f?.name).filter(Boolean) as string[]
          if (names.length) _flowsCache = names
          if (!cancelled) setServerNames(names)
        }
      } catch {
        /* server down → fall back to the hardcoded catalog below */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // ALL flows on ALL boards — the run component is universal (no per-board filtering). Known
  // flows first (curated order), then the rest alphabetically. handleRunFlow routes each to the
  // right endpoint (project-consultation → project-decompose); flows that need a feature storage
  // dir only /runner/start-run on a feature board until the backend scope guard is relaxed.
  const orderedNames = useMemo(() => {
    const names = serverNames.length ? serverNames : BOARD_FLOWS.map((f) => f.key)
    const knownFirst = BOARD_FLOWS.map((f) => f.key).filter((k) => names.includes(k))
    const others = names.filter((n) => !KNOWN.has(n)).sort()
    return [...knownFirst, ...others]
  }, [serverNames])

  // Keep the selection valid as the list loads; default the project board to its own flow.
  useEffect(() => {
    if (!orderedNames.length || orderedNames.includes(flowKey)) return
    const preferred =
      boardKey === 'project' && orderedNames.includes('project-consultation')
        ? 'project-consultation'
        : orderedNames[0]
    setFlowKey(preferred)
  }, [orderedNames, flowKey, boardKey])

  const options: BoardSelectOption[] = orderedNames.map((name) => {
    const k = KNOWN.get(name)
    return { value: name, label: k?.label ?? name, hint: k?.blurb ?? 'Pathly flow' }
  })
  const knownFlow = KNOWN.get(flowKey)

  function run(): void {
    if (running || !flowKey) return
    onRunFlow(flowKey, { interactive })
    onClose()
  }

  return (
    <>
      <div className={s.body}>
        <label className={s.label} htmlFor="flow-pick">Flow</label>
        <BoardSelect id="flow-pick" ariaLabel="Flow" value={flowKey} options={options} onChange={setFlowKey} />

        {knownFlow ? (
          <>
            <FlowDiagram flow={knownFlow} />
            <FlowAbout flow={knownFlow} />
          </>
        ) : (
          <p className={s.modeHint}>
            Runs the <code>{flowKey}</code> flow’s full stage pipeline on this board’s topic.
          </p>
        )}

        <p className={s.modeHint}>
          Runs the whole flow on this board’s topic — no goal or task DAG needed. Stages spawn as terminals, just like the Start button.
        </p>
      </div>

      <div className={s.modeBand}>
        <span className={s.label}>Mode</span>
        <div className={s.modeRow} role="radiogroup" aria-label="Run mode">
          <button
            type="button"
            className={s.modeBtn}
            {...(!interactive ? { 'data-on': '' } : {})}
            {...(!interactive ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
            role="radio"
            onClick={() => setInteractive(false)}
          >
            Headless
          </button>
          <button
            type="button"
            className={s.modeBtn}
            {...(interactive ? { 'data-on': '' } : {})}
            {...(interactive ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
            role="radio"
            onClick={() => setInteractive(true)}
          >
            Interactive
          </button>
        </div>
        <p className={s.modeHint}>
          {interactive
            ? 'Each stage opens a live terminal you can watch and steer.'
            : 'Each stage runs headless; progress posts to the board and terminals.'}
        </p>
      </div>

      <footer className={s.footer}>
        <span className={s.spacer} />
        <button type="button" className={s.btnQuiet} onClick={onClose}>Cancel</button>
        <button
          type="button"
          className={s.btnRun}
          onClick={run}
          disabled={running || !flowKey}
          title={running ? 'A run is already active on this board' : undefined}
        >
          <Play size={12} /> Run flow
        </button>
      </footer>
    </>
  )
}
