import { useState } from 'react'
import { Play } from 'lucide-react'
import { BOARD_FLOWS } from './flowCatalog'
import { FlowDiagram } from './FlowDiagram/FlowDiagram'
import { FlowAbout } from './FlowAbout/FlowAbout'
import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import s from './SingleAgentButton.module.css'

interface Props {
  running: boolean
  onRunFlow: (flow: string, opts: { interactive: boolean }) => void
  onClose: () => void
}

const FLOW_OPTIONS: BoardSelectOption[] = BOARD_FLOWS.map((f) => ({ value: f.key, label: f.label, hint: f.blurb }))

// Flow mode of the run modal: pick a board-scoped flow, preview its stage pipeline,
// then run the whole flow on this board's topic (no goal/DAG required). Mode lives in
// a pinned band so it stays reachable even when the diagram + About push the body tall.
export function FlowForm({ running, onRunFlow, onClose }: Props): JSX.Element {
  const [flowKey, setFlowKey] = useState<string>(BOARD_FLOWS[0].key)
  const [interactive, setInteractive] = useState(true)
  const flow = BOARD_FLOWS.find((f) => f.key === flowKey) ?? BOARD_FLOWS[0]

  function run(): void {
    if (running) return
    onRunFlow(flow.key, { interactive })
    onClose()
  }

  return (
    <>
      <div className={s.body}>
        <label className={s.label} htmlFor="flow-pick">Flow</label>
        <BoardSelect id="flow-pick" ariaLabel="Flow" value={flowKey} options={FLOW_OPTIONS} onChange={setFlowKey} />

        <FlowDiagram flow={flow} />
        <FlowAbout flow={flow} />

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
          disabled={running}
          title={running ? 'A run is already active on this board' : undefined}
        >
          <Play size={12} /> Run flow
        </button>
      </footer>
    </>
  )
}
