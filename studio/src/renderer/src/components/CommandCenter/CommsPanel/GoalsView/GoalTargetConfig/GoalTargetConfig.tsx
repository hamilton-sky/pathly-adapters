import { Zap } from 'lucide-react'
import CliSelect from '../../../../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { BoardSelect } from '../../../../shared/BoardSelect/BoardSelect'
import { MODE_OPTIONS } from '../planRigor'
import type { DecomposeMode } from '../../../../../store/commsApi'
import type { EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import s from './GoalTargetConfig.module.css'

interface Props {
  rigorMode: DecomposeMode
  selectedCli: EditorCli
  /** A run this control dispatched is live — lock Rigor so it can't desync mid-run. */
  running: boolean
  onRigorChange: (mode: DecomposeMode) => void
  onCliChange: (cli: EditorCli) => void
  onRun: () => void
}

// The goal-target path of the evaluator popover: pick planning rigor + engine, then
// "Plan now" runs the decompose. Shown when a specific goal (not the whole board) is
// the Evaluate target.
export function GoalTargetConfig({
  rigorMode, selectedCli, running, onRigorChange, onCliChange, onRun,
}: Props): JSX.Element {
  return (
    <>
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-rigor">RIGOR</label>
        <BoardSelect
          id="eval-rigor"
          ariaLabel="Planning rigor"
          value={rigorMode}
          options={MODE_OPTIONS}
          onChange={(v) => onRigorChange(v as DecomposeMode)}
          leadingIcon={<Zap size={13} />}
          disabled={running}
        />
      </section>

      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={selectedCli} onChange={onCliChange} align="right" up />
      </section>

      <div className={s.footer}>
        <button type="button" className={s.runBtn} onClick={onRun} disabled={running}>
          Plan now
        </button>
      </div>
    </>
  )
}
