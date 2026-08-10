import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import { useNewRunForm, type RunKind, type RunBoard } from './hooks/useNewRunForm'
import { useProjectFeatures } from './hooks/useProjectFeatures'
import s from './NewRunButton.module.css'

interface Props {
  projectRoot: string
  defaultScope: string
  onCancel: () => void
  onSuccess: () => void
}

const KIND_OPTIONS: BoardSelectOption[] = [
  { value: 'flow', label: 'Flow', hint: 'Full stage pipeline · start_run' },
  { value: 'single', label: 'Single agent', hint: 'One board-scoped agent' },
  { value: 'evaluator', label: 'Evaluator', hint: 'Board-scoped evaluate pass' },
  { value: 'goal', label: 'Goal', hint: 'Dispatch a goal’s task-DAG' },
]

const BOARD_OPTIONS: BoardSelectOption[] = [
  { value: 'feature', label: 'Feature' },
  { value: 'project', label: 'Project' },
  { value: 'global', label: 'Global' },
]

// Fields for the unified /runs launcher (T5/T6): kind, board and scope always; flow only for
// kind='flow', goal_id only for kind='goal' (board/scope are harmless-if-unused for 'goal' —
// keeping them visible avoids reshuffling the form on every kind change).
export function NewRunForm({ projectRoot, defaultScope, onCancel, onSuccess }: Props): JSX.Element {
  const { form, setKind, setBoard, setScope, setFlow, setGoalId, submitting, error, canSubmit, submit } =
    useNewRunForm(projectRoot, defaultScope)
  const features = useProjectFeatures(projectRoot)

  async function handleSubmit(): Promise<void> {
    if (await submit()) onSuccess()
  }

  return (
    <>
      <div className={s.body}>
        <label className={s.label} htmlFor="new-run-kind">Kind</label>
        <BoardSelect
          id="new-run-kind"
          ariaLabel="Run kind"
          value={form.kind}
          options={KIND_OPTIONS}
          onChange={(v) => setKind(v as RunKind)}
        />

        <label className={s.label} htmlFor="new-run-board">Board</label>
        <BoardSelect
          id="new-run-board"
          ariaLabel="Board"
          value={form.board}
          options={BOARD_OPTIONS}
          onChange={(v) => setBoard(v as RunBoard)}
        />

        <label className={s.label} htmlFor="new-run-scope">Scope</label>
        {form.board === 'feature' && features.length > 0 ? (
          // Pick an existing feature (GET /db/features) instead of typing a slug.
          <BoardSelect
            id="new-run-scope"
            ariaLabel="Scope (feature)"
            value={form.scope}
            options={features.map((f) => ({ value: f, label: f }))}
            onChange={setScope}
            placeholder="select a feature…"
          />
        ) : (
          // project/global board, or a project with no features yet → free-text fallback.
          <input
            id="new-run-scope"
            className={s.input}
            type="text"
            placeholder="feature slug / board scope"
            value={form.scope}
            onChange={(e) => setScope(e.currentTarget.value)}
          />
        )}

        {form.kind === 'flow' && (
          <>
            <label className={s.label} htmlFor="new-run-flow">Flow</label>
            <input
              id="new-run-flow"
              className={s.input}
              type="text"
              placeholder="e.g. team, consultation, feature-consultation"
              value={form.flow}
              onChange={(e) => setFlow(e.currentTarget.value)}
            />
          </>
        )}

        {form.kind === 'goal' && (
          <>
            <label className={s.label} htmlFor="new-run-goal">Goal id</label>
            <input
              id="new-run-goal"
              className={s.input}
              type="text"
              placeholder="goal message id"
              value={form.goalId}
              onChange={(e) => setGoalId(e.currentTarget.value)}
            />
          </>
        )}

        {error && <p className={s.error}>{error}</p>}
      </div>

      <div className={s.footer}>
        <span className={s.spacer} />
        <button type="button" className={s.btnQuiet} onClick={onCancel}>Cancel</button>
        <button
          type="button"
          className={s.btnRun}
          disabled={!canSubmit || submitting}
          onClick={() => void handleSubmit()}
        >
          {submitting ? 'Starting…' : 'Start run'}
        </button>
      </div>
    </>
  )
}
