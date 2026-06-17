import { Sparkles } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { useCommsStore } from '../../../../store/commsStore'
import s from './GoalsView.module.css'

interface Props {
  /** Board key: feature id, 'project', or 'global'. */
  boardKey: string
}

// Surfaces the evaluator "starting point": reads everything on this board
// (messages, decisions, dropped notes), classifies it (CODE/RESEARCH/BOTH), and
// posts concrete task proposals — which then appear here as a DAG to Run. Shares
// the board run-state, so it goes busy while any board agent is running.
export function EvaluateBoardButton({ boardKey }: Props): JSX.Element {
  const runEvaluator = useCommsStore((st) => st.runEvaluator)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const running = boardRunState[boardKey] === 'running'

  return (
    <Tooltip label="Evaluate board" description="Analyze everything on this board and propose concrete tasks" placement="bottom">
      <button
        type="button"
        className={s.evalBtn}
        disabled={running}
        onClick={() => runEvaluator(boardKey)}
      >
        <Sparkles size={13} />
        <span className={s.newGoalLabel}>{running ? 'Evaluating…' : 'Evaluate'}</span>
      </button>
    </Tooltip>
  )
}
