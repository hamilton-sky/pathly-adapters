import { useMemo } from 'react'
import type { DecomposeMode } from '../../../../../store/commsApi'

// Reconstruct the decompose directive the server assembles, as faithfully as the renderer
// can — a representative preview, not a verbatim copy.
//
//  • planner  → mirrors supervisor/goal_run.py _decompose_planner: the planner runs on the
//               goal's scope with a directive that the goal ALREADY exists, so it stamps every
//               type=task with this goal_id (plan.md Step 6) instead of posting a new goal.
//  • consultation → mirrors _decompose_consultation: the heavy PO→architect→researcher→
//               designer→planner FSM flow runs on the goal's scope; its planner stage seeds
//               the DAG. (No single directive string — the flow's per-stage skills drive it —
//               so this is a representative summary of what runs.)
//
// The skill body is composed server-side at spawn time, so (like useEvaluatePreview) it can't
// be shown verbatim here; the trailing note says so.
export function useDecomposePreview(mode: DecomposeMode, goalText: string): string {
  return useMemo(() => {
    const goalLine = goalText.trim() ? `Goal: ${goalText.trim()}` : 'Goal: (the selected goal)'
    if (mode === 'consultation') {
      return [
        '# Decompose via consultation (deep · full team)',
        'Run the consultation flow on this goal: PO → architect → researcher → designer → planner.',
        'The planner stage seeds the task DAG under this goal.',
        '',
        goalLine,
        '',
        '---',
        '_The consultation flow runs headless (no terminal input). Each stage composes its own skill prompt at spawn time, so the exact per-stage prompts are not shown verbatim above._',
      ].join('\n')
    }
    return [
      '# Decompose via planner (fast · DAG only)',
      'Decompose the EXISTING goal into a task DAG.',
      '',
      goalLine,
      '',
      'Produce the plan files, then execute plan.md Step 6 to post one type=task per phase — '
        + 'but the goal already exists, so do NOT post a new type=goal; stamp every task with this goal_id. '
        + 'The posted tasks are this goal\'s DAG.',
      '',
      '---',
      '_The planner skill body is composed server-side at spawn time, so it is not shown verbatim above._',
    ].join('\n')
  }, [mode, goalText])
}
