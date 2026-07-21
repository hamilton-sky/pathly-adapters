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
  /** Open the flow gate preview for the picked flow. The PARENT closes this run dialog and shows
   *  the gate as the sole modal — so the gate appears INSTEAD of this modal, not stacked under it
   *  (the run modal sits at a high z-index; a gate rendered inside it would render beneath it). */
  onOpenGate: (flow: string, interactive: boolean) => void
  onClose: () => void
}

const KNOWN = new Map(BOARD_FLOWS.map((f) => [f.key, f]))

// Flow mode of the run modal: pick ANY Pathly flow (fetched live from GET /flows, so
// consultation + user-created flows appear — not just the 5 hardcoded ones), preview it, then run
// the whole flow on this board's topic. Known flows get the rich diagram + About; others show a
// terse note. Falls back to the hardcoded catalog if the server is unreachable.
// Cached so switching to the Flow tab (which re-mounts this form) doesn't re-fetch and flicker.
let _flowsCache: string[] | null = null

// Known flows first (curated BOARD_FLOWS order), then any others alphabetically — the ONE ordering
// used by both the initial selection and the live-loaded list, so they can never disagree.
function orderFlowNames(names: string[]): string[] {
  const knownFirst = BOARD_FLOWS.map((f) => f.key).filter((k) => names.includes(k))
  const others = names.filter((n) => !KNOWN.has(n)).sort()
  return [...knownFirst, ...others]
}
// Default pick for a board: the project board's own consultation, else the first ordered flow.
function defaultFlowKey(names: string[], boardKey: string): string {
  const ordered = orderFlowNames(names)
  if (boardKey === 'project' && ordered.includes('project-consultation')) return 'project-consultation'
  return ordered[0] ?? ''
}

export function FlowForm({ boardKey, running, onOpenGate, onClose }: Props): JSX.Element {
  const [serverNames, setServerNames] = useState<string[]>(_flowsCache ?? [])
  // Seed the selection SYNCHRONOUSLY (from the cache, or the built-in catalog) so the very first
  // paint already has a known flow and the FlowDiagram renders immediately. Starting at '' rendered
  // the terse "unknown flow" note for one frame before an effect set the key — the tab-switch flicker.
  const [flowKey, setFlowKey] = useState<string>(
    () => defaultFlowKey(_flowsCache ?? BOARD_FLOWS.map((f) => f.key), boardKey),
  )
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
  const orderedNames = useMemo(
    () => orderFlowNames(serverNames.length ? serverNames : BOARD_FLOWS.map((f) => f.key)),
    [serverNames],
  )

  // Safety net: re-default only if the live list drops the current pick (the initializer already
  // seeded a valid one, so this is a no-op on the common path — no flicker).
  useEffect(() => {
    if (!orderedNames.length || orderedNames.includes(flowKey)) return
    setFlowKey(defaultFlowKey(orderedNames, boardKey))
  }, [orderedNames, flowKey, boardKey])

  const options: BoardSelectOption[] = orderedNames.map((name) => {
    const k = KNOWN.get(name)
    return { value: name, label: k?.label ?? name, hint: k?.blurb ?? 'Pathly flow' }
  })
  const knownFlow = KNOWN.get(flowKey)

  // "Run flow" no longer runs immediately — it opens the flow-specific gate preview
  // (stepper + per-stage banner + Sections) so the human can see/trim each stage's
  // composed prompt before any agent spawns. Confirming the gate is what actually runs.
  function openGate(): void {
    if (running || !flowKey) return
    onOpenGate(flowKey, interactive)
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
          onClick={openGate}
          disabled={running || !flowKey}
          title={running ? 'A run is already active on this board' : undefined}
        >
          <Play size={12} /> Run flow
        </button>
      </footer>
    </>
  )
}
