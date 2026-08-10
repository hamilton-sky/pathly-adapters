import { useState } from 'react'
import { apiCreateRun, type RunSpec } from '../../../../../store/commsApi'

export type RunKind = RunSpec['kind']
export type RunBoard = NonNullable<RunSpec['board']>

interface FormState {
  kind: RunKind
  board: RunBoard
  scope: string
  flow: string
  goalId: string
}

interface UseNewRunForm {
  form: FormState
  setKind: (kind: RunKind) => void
  setBoard: (board: RunBoard) => void
  setScope: (scope: string) => void
  setFlow: (flow: string) => void
  setGoalId: (goalId: string) => void
  submitting: boolean
  error: string | null
  canSubmit: boolean
  submit: () => Promise<boolean>
}

// Form state + submit for the New-run launcher (POST /runs, T6). Validation mirrors the
// server's own per-kind requirements (control/_helpers.create_run): flow needs scope+flow,
// single/evaluator need scope, goal needs goal_id — so Start stays disabled instead of
// round-tripping a 400.
export function useNewRunForm(projectRoot: string, defaultScope: string): UseNewRunForm {
  const [form, setForm] = useState<FormState>({
    kind: 'flow',
    board: 'feature',
    scope: defaultScope,
    flow: '',
    goalId: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit =
    form.kind === 'goal'
      ? form.goalId.trim().length > 0
      : form.kind === 'flow'
        ? form.scope.trim().length > 0 && form.flow.trim().length > 0
        : form.scope.trim().length > 0

  async function submit(): Promise<boolean> {
    if (!canSubmit || submitting) return false
    setSubmitting(true)
    setError(null)
    const res = await apiCreateRun({
      kind: form.kind,
      board: form.board,
      scope: form.scope.trim(),
      flow: form.kind === 'flow' ? form.flow.trim() : undefined,
      goalId: form.kind === 'goal' ? form.goalId.trim() : undefined,
      projectRoot,
    })
    setSubmitting(false)
    if (!res || !res.ok) {
      setError(res?.error ?? 'Could not start the run.')
      return false
    }
    return true
  }

  return {
    form,
    setKind: (kind) => setForm((f) => ({ ...f, kind })),
    setBoard: (board) => setForm((f) => ({ ...f, board })),
    setScope: (scope) => setForm((f) => ({ ...f, scope })),
    setFlow: (flow) => setForm((f) => ({ ...f, flow })),
    setGoalId: (goalId) => setForm((f) => ({ ...f, goalId })),
    submitting,
    error,
    canSubmit,
    submit,
  }
}
