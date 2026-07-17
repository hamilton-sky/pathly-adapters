import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../../../../store'
import { composeSkillPrompt, type ComposedSegment } from '../../../../../services/skillCompose'

const BUILD_SKILL = 'development/build'

// The REAL prompt the server assembles for a per-task run: the development/build skill COMPOSED
// with its Pathly fragments (+ any selected abilities), then the "build EXACTLY this one task"
// directive carrying the task text, then a note that the live board context is appended at spawn.
//
// It COMPOSES (POST /skills/compose) so a Sections trim can be sent verbatim as prompt_override —
// a fragment-less body would write no AGENT_DONE (the run vanishes + goes unbilled). The "build
// only this task" directive + task text MUST be part of the preview because the override REPLACES
// the whole prompt server-side. Mirrors /comms/tasks/run in blueprints/comms/tasks.py.
export function useTaskRunPreview(
  enabled: boolean,
  taskText: string,
  abilityIds: string[],
): { prompt: string; segments: ComposedSegment[] } {
  const projectPath = useStore((st) => st.projectPath)
  const abilityKey = abilityIds.join(',')
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
    void composeSkillPrompt(BUILD_SKILL, { projectRoot: projectPath, abilityIds }).then((r) => {
      if (!cancelled) setComposed(r)
    })
    return () => {
      cancelled = true
    }
    // abilityKey stands in for the abilityIds array (stable identity across renders).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, projectPath, abilityKey])

  const prompt = useMemo(() => {
    return [
      composed?.prompt?.trim() || `# Builder\n_(The ${BUILD_SKILL} skill composes at spawn time.)_`,
      '## Task\n\nBuild EXACTLY this one task and nothing else — it is a self-contained builder ' +
        'prompt (what to build · Files · Done when). Do not start other tasks.\n\n' +
        taskText.trim(),
      '---\n_Live board context is appended automatically when the engine runs, so it is not ' +
        'shown verbatim above._',
    ].join('\n\n')
  }, [composed, taskText])

  return { prompt, segments: composed?.segments ?? [] }
}
