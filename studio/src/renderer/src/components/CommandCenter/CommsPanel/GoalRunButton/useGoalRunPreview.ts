import { useMemo } from 'react'
import { useStore } from '../../../../store'
import { usePromptContent } from '../../../shared/PromptPreview/PromptPreview'
import { useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'

// Executor → the skill the spawned agent actually runs (mirrors supervisor/goal_executor.py):
// `single` drains the whole DAG in one agent (drain-dag); `loop` runs one task per spawn
// (execute-task); `team` runs a multi-stage FSM flow, so there is no single skill body to show.
const EXECUTOR_SKILL: Record<string, string> = {
  single: 'development/drain-dag',
  loop: 'development/execute-task',
}

// Reconstruct the prompt a goal run sends, as faithfully as the renderer can — mirrors
// supervisor/goal_executor.py: the goal, then the executor's skill body, then a note that the
// live task-DAG and board context are appended at spawn time (so they can't be shown verbatim).
// Fetches the skill only while `enabled` (the preview modal is open) to avoid idle reads.
export function useGoalRunPreview(
  enabled: boolean,
  executor: string,
  goalText: string,
  taskLine: string,
): string {
  const projectPath = useStore((st) => st.projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const skillRel = EXECUTOR_SKILL[executor] ?? ''
  const skillBody = usePromptContent(
    enabled && skillRel ? skillRel : '',
    'src/pathly_data/core/skills', skillCatalog,
    skillRel ? { [skillRel]: skillRel } : {}, {}, projectPath,
  )

  return useMemo(() => {
    const parts: string[] = [
      `# Goal\n\n${goalText.trim() || '_(untitled goal)_'}\n\n_${taskLine}_`,
    ]
    if (skillRel) {
      parts.push(
        skillBody?.trim() ||
          `# ${skillRel}\n_(The skill body loads from the project at spawn time.)_`,
      )
    } else {
      parts.push(
        '# Team executor\n\nRuns the multi-stage `team-build` FSM flow — each stage spawns its ' +
          'own agent with a per-stage prompt, so no single prompt is sent up front.',
      )
    }
    parts.push(
      '---\n_The live task-DAG for this goal and the board context are appended automatically ' +
        'when the engine runs, so they are not shown verbatim above._',
    )
    return parts.join('\n\n')
  }, [skillBody, skillRel, goalText, taskLine])
}
