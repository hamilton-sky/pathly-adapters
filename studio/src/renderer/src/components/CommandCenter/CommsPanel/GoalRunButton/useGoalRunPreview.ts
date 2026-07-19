import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../../../store'
import { composeSkillPrompt, type ComposedSegment } from '../../../../services/skillCompose'
import { executorInfo } from './executorInfo'

// The prompt a goal run sends, as faithfully as the renderer can — mirrors
// supervisor/goal_executor.py: the goal, then the executor's COMPOSED skill body (skill +
// Pathly fragments), then a note that the live task-DAG + board context are appended at spawn.
//
// It COMPOSES (POST /skills/compose) rather than reading the raw skill file, so the gate shows
// the FULL prompt — skill + fragments — and the returned segments drive the Sections modal's
// layer tabs + fragment lock. 'team' has no single skill (multi-stage FSM flow), so it keeps a
// note. Composes only while `enabled` (the preview modal is open).
export function useGoalRunPreview(
  enabled: boolean,
  executor: string,
  goalText: string,
  taskLine: string,
  abilityIds: string[] = [],
): { prompt: string; segments: ComposedSegment[] } {
  const projectPath = useStore((st) => st.projectPath)
  const skillRel = executorInfo(executor).skillRel
  const abilityKey = abilityIds.join(',')
  const [composed, setComposed] = useState<{
    prompt: string
    segments: ComposedSegment[]
  } | null>(null)

  useEffect(() => {
    if (!enabled || !skillRel) {
      setComposed(null)
      return
    }
    let cancelled = false
    void composeSkillPrompt(skillRel, { projectRoot: projectPath, abilityIds }).then((r) => {
      if (!cancelled) setComposed(r)
    })
    return () => {
      cancelled = true
    }
    // abilityKey stands in for the abilityIds array (stable identity across renders).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, skillRel, projectPath, abilityKey])

  const prompt = useMemo(() => {
    const parts: string[] = [
      `# Goal\n\n${goalText.trim() || '_(untitled goal)_'}\n\n_${taskLine}_`,
    ]
    if (skillRel) {
      parts.push(
        composed?.prompt?.trim() ||
          `# ${skillRel}\n_(The ${skillRel} skill composes at spawn time.)_`,
      )
    } else {
      parts.push(
        '# Team executor\n\nRuns the multi-stage `team-build` FSM flow: BUILDING (builder) → ' +
          'REVIEWING (reviewer) → TESTING (tester) → RETRO. Each stage spawns its own agent with ' +
          'a per-stage skill, so no single prompt is sent up front.',
      )
    }
    parts.push(
      '---\n_The live task-DAG for this goal and the board context are appended automatically ' +
        'when the engine runs, so they are not shown verbatim above._',
    )
    return parts.join('\n\n')
  }, [composed, skillRel, goalText, taskLine])

  return { prompt, segments: composed?.segments ?? [] }
}
