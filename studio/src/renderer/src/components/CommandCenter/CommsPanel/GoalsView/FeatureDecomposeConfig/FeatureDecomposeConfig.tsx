import { GitFork } from 'lucide-react'
import CliSelect from '../../../../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { BoardSelect } from '../../../../shared/BoardSelect/BoardSelect'
import type { EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
// Same visual language as the per-goal RIGOR ladder one level up.
import s from '../GoalTargetConfig/GoalTargetConfig.module.css'

export type FeatureRigor = 'light' | 'full' | 'consultation'

/** Target-selector sentinel for "Whole board — Decompose into goals" (never a real goal id). */
export const DECOMPOSE_TARGET = '__decompose__'

const RIGOR_OPTIONS: { value: FeatureRigor; label: string; hint: string }[] = [
  { value: 'light', label: 'Light', hint: 'One planner run posts the sibling goals — fast' },
  { value: 'full', label: 'Full', hint: 'A richer planner pass before seeding goals' },
  {
    value: 'consultation',
    label: 'Consultation',
    hint: 'PO → architect → research → design → planner, then seed goals — slow, thorough',
  },
]

interface Props {
  rigor: FeatureRigor
  selectedCli: EditorCli
  /** A run is live — lock the controls so they can't desync mid-run. */
  running: boolean
  onRigorChange: (r: FeatureRigor) => void
  onCliChange: (cli: EditorCli) => void
  onRun: () => void
}

// The board-decompose path of the evaluator popover — mirrors GoalTargetConfig's shape
// (rigor + engine + one primary button) one altitude up: board → sibling goals instead of
// goal → task DAG. Shown when the Target selector picks "Whole board — Decompose into
// goals"; dispatches feature-decompose (POST /comms/features/decompose).
export function FeatureDecomposeConfig({
  rigor, selectedCli, running, onRigorChange, onCliChange, onRun,
}: Props): JSX.Element {
  return (
    <>
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="featdec-rigor">RIGOR</label>
        <BoardSelect
          id="featdec-rigor"
          ariaLabel="Decompose rigor"
          value={rigor}
          options={RIGOR_OPTIONS}
          onChange={(v) => onRigorChange(v as FeatureRigor)}
          leadingIcon={<GitFork size={13} />}
          disabled={running}
        />
      </section>

      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={selectedCli} onChange={onCliChange} align="right" up />
      </section>

      <div className={s.footer}>
        <button type="button" className={s.runBtn} onClick={onRun} disabled={running}>
          {running ? 'Decomposing…' : 'Decompose into goals'}
        </button>
      </div>
    </>
  )
}
