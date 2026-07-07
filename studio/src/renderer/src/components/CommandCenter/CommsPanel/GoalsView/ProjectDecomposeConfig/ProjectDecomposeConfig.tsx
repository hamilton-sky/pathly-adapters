import { GitFork } from 'lucide-react'
import CliSelect from '../../../../MarkdownEditor/EditorHeader/CliSelect/CliSelect'
import { BoardSelect } from '../../../../shared/BoardSelect/BoardSelect'
import type { EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import type { FeatureRigor } from '../FeatureDecomposeConfig/FeatureDecomposeConfig'
// Same visual language as the per-goal RIGOR ladder + the feature-decompose config one
// altitude down — shared across all three tiers.
import s from '../GoalTargetConfig/GoalTargetConfig.module.css'

export type ProjectRigor = FeatureRigor

const RIGOR_OPTIONS: { value: ProjectRigor; label: string; hint: string }[] = [
  { value: 'light', label: 'Light', hint: 'One planner run posts the sibling features — fast' },
  { value: 'full', label: 'Full', hint: 'A richer planner pass before seeding features' },
  {
    value: 'consultation',
    label: 'Consultation',
    hint: 'PO → architect → research → design → planner, then seed features — slow, thorough',
  },
]

interface Props {
  rigor: ProjectRigor
  selectedCli: EditorCli
  /** A run is live — lock the controls so they can't desync mid-run. */
  running: boolean
  onRigorChange: (r: ProjectRigor) => void
  onCliChange: (cli: EditorCli) => void
  onRun: () => void
}

// The board-decompose path of the evaluator popover — mirrors FeatureDecomposeConfig's
// shape (rigor + engine + one primary button) one altitude up: PROJECT board → sibling
// FEATURES instead of feature board → sibling goals. Shown when the Target selector picks
// "Whole board — Decompose into features" on the project board; dispatches
// project-decompose (POST /comms/project/decompose).
export function ProjectDecomposeConfig({
  rigor, selectedCli, running, onRigorChange, onCliChange, onRun,
}: Props): JSX.Element {
  return (
    <>
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="projdec-rigor">RIGOR</label>
        <BoardSelect
          id="projdec-rigor"
          ariaLabel="Decompose rigor"
          value={rigor}
          options={RIGOR_OPTIONS}
          onChange={(v) => onRigorChange(v as ProjectRigor)}
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
          {running ? 'Decomposing…' : 'Decompose into features'}
        </button>
      </div>
    </>
  )
}
