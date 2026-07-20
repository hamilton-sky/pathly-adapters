import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../../../store'
import { composeSkillPrompt, type ComposedSegment } from '../../../../services/skillCompose'

const EVAL_SKILL_REL = 'planning/evaluate'

// The REAL prompt the server assembles for a board evaluation: the evaluator skill COMPOSED
// with its Pathly fragments (comms-post + completion-report), then the user's lens
// (## System instructions) and extra (## Task), then a note that the live board context is
// appended at spawn and so can't be shown verbatim.
//
// It COMPOSES (POST /skills/compose) rather than reading the raw evaluate.md, because this
// text is what a Sections config sends verbatim as prompt_override — a fragment-less body
// would make the run post no BOARD_EVAL artifact and write no AGENT_DONE (it would vanish
// from the Monitor's RECENT list and go unbilled). Composes only while `enabled` (the gate
// is open) to avoid idle work.
export function useEvaluatePreview(
  enabled: boolean,
  lensText: string,
  extraPrompt: string,
): { prompt: string; segments: ComposedSegment[] } {
  const projectPath = useStore((st) => st.projectPath)
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
    void composeSkillPrompt(EVAL_SKILL_REL, { projectRoot: projectPath }).then((r) => {
      if (!cancelled) setComposed(r)
    })
    return () => {
      cancelled = true
    }
  }, [enabled, projectPath])

  const prompt = useMemo(() => {
    const parts: string[] = [
      composed?.prompt?.trim() ||
        '# Built-in evaluator\n_(The evaluator prompt composes at spawn time.)_',
    ]
    if (lensText.trim()) parts.push('## System instructions\n\n' + lensText.trim())
    if (extraPrompt.trim()) parts.push('## Task\n\n' + extraPrompt.trim())
    parts.push(
      '---\n_Live board context — every message and artifact on this board — is appended automatically when the engine runs, so it is not shown verbatim above._',
    )
    return parts.join('\n\n')
  }, [composed, lensText, extraPrompt])

  return { prompt, segments: composed?.segments ?? [] }
}
