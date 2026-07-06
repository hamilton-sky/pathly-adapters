import { GitFork } from 'lucide-react'
import { BoardSelect } from '../../../../shared/BoardSelect/BoardSelect'
// Same visual language as the per-goal RIGOR ladder one level up.
import s from '../GoalTargetConfig/GoalTargetConfig.module.css'

export type FeatureRigor = 'light' | 'full' | 'consultation'

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
  /** A run is live — lock the selector + button so it can't desync mid-run. */
  running: boolean
  onRigorChange: (r: FeatureRigor) => void
  onRun: () => void
}

// Whole-board "Decompose into goals": pick a rigor tier, then dispatch feature-decompose
// (POST /comms/features/decompose → sibling goals on the board). The alternative whole-board
// action to Evaluate. Engine is inherited from the popover's shared engine picker.
export function FeatureDecomposeConfig({ rigor, running, onRigorChange, onRun }: Props): JSX.Element {
  return (
    <section className={s.section}>
      <label className={s.sectionLabel} htmlFor="featdec-rigor">DECOMPOSE INTO GOALS</label>
      <BoardSelect
        id="featdec-rigor"
        ariaLabel="Decompose rigor"
        value={rigor}
        options={RIGOR_OPTIONS}
        onChange={(v) => onRigorChange(v as FeatureRigor)}
        leadingIcon={<GitFork size={13} />}
        disabled={running}
      />
      <button type="button" className={s.runBtn} onClick={onRun} disabled={running}>
        {running ? 'Decomposing…' : 'Decompose into goals'}
      </button>
    </section>
  )
}
