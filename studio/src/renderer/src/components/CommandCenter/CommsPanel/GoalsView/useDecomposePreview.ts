import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../../../store'
import { composeSkillPrompt, type ComposedSegment } from '../../../../services/skillCompose'
import type { DecomposeMode } from '../../../../store/commsApi'

// Which planner skill each decompose rigor composes — mirrors supervisor/goal_decomposer.py:
//   planner → planning/dag-sketch (light, DAG-only) · plan → planning/plan (full plan + DAG).
// 'consultation' is an FSM flow (no single prompt) and never reaches this preview gate.
const MODE_SKILL: Record<string, string> = {
  planner: 'planning/dag-sketch',
  plan: 'planning/plan',
}

// The REAL prompt the server assembles for a per-goal decompose: the planner skill COMPOSED
// with its Pathly fragments (+ any selected abilities), then the decompose task directive, then
// a note that the live board context is appended at spawn.
//
// It COMPOSES (POST /skills/compose) so a Sections trim can be sent verbatim as prompt_override
// — a fragment-less body would post no tasks / write no AGENT_DONE. The task directive (goal_id +
// "post children only") MUST be part of the preview because the override REPLACES the whole
// prompt server-side: without it, a trimmed run could post a new goal instead of task children.
// Mirrors _decompose_planner / _decompose_plan in supervisor/goal_decomposer.py.
export function useDecomposePreview(
  enabled: boolean,
  mode: DecomposeMode,
  goalText: string,
  goalId: string,
): { prompt: string; segments: ComposedSegment[] } {
  const projectPath = useStore((st) => st.projectPath)
  const skillRel = MODE_SKILL[mode] ?? 'planning/plan'
  const [composed, setComposed] = useState<{
    prompt: string
    segments: ComposedSegment[]
  } | null>(null)

  useEffect(() => {
    if (!enabled) {
      setComposed(null)
      return
    }
    let cancelled = false
    void composeSkillPrompt(skillRel, { projectRoot: projectPath }).then((r) => {
      if (!cancelled) setComposed(r)
    })
    return () => {
      cancelled = true
    }
  }, [enabled, skillRel, projectPath])

  const prompt = useMemo(() => {
    const parts: string[] = [
      composed?.prompt?.trim() || `# Planner\n_(The ${skillRel} skill composes at spawn time.)_`,
    ]
    parts.push(
      goalText.trim()
        ? `## Task\n\nDecompose this goal into a concrete, independently-runnable task DAG.\n\n` +
            `**Goal:** ${goalText.trim()}\n\nThe goal already exists (goal_id \`${goalId}\`) — ` +
            `post task children only, do NOT post a new goal.`
        : `## Task\n\nDecompose the selected goal (goal_id \`${goalId}\`) into a task DAG — ` +
            `post task children only, do NOT post a new goal.`,
    )
    parts.push(
      '---\n_Live board context — every message and artifact on this board — is appended ' +
        'automatically when the engine runs, so it is not shown verbatim above._',
    )
    return parts.join('\n\n')
  }, [composed, skillRel, goalText, goalId])

  return { prompt, segments: composed?.segments ?? [] }
}
