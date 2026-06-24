import { useMemo } from 'react'
import { useStore } from '../../../../store'
import { usePromptContent } from '../../../shared/PromptPreview/PromptPreview'
import { useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'

const EVAL_SKILL_REL = 'planning/evaluate'

// Reconstruct the prompt the server assembles for a board evaluation, as faithfully as the
// renderer can — mirrors supervisor/board_run.py: the evaluator skill body, then the user's
// lens (## System instructions) and extra (## Task), then a note that the live board context
// (every message + artifact) is appended at spawn time and so can't be shown verbatim here.
// Fetches the skill only while `enabled` (the confirm modal is open) to avoid idle reads.
export function useEvaluatePreview(enabled: boolean, lensText: string, extraPrompt: string): string {
  const projectPath = useStore((st) => st.projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const evaluatorBody = usePromptContent(
    enabled ? EVAL_SKILL_REL : '',
    'src/pathly_data/core/skills', skillCatalog,
    { [EVAL_SKILL_REL]: EVAL_SKILL_REL }, {}, projectPath,
  )

  return useMemo(() => {
    const parts: string[] = [
      evaluatorBody?.trim() || '# Built-in evaluator\n_(The evaluator skill body loads from the project at spawn time.)_',
    ]
    if (lensText.trim()) parts.push('## System instructions\n\n' + lensText.trim())
    if (extraPrompt.trim()) parts.push('## Task\n\n' + extraPrompt.trim())
    parts.push('---\n_Live board context — every message and artifact on this board — is appended automatically when the engine runs, so it is not shown verbatim above._')
    return parts.join('\n\n')
  }, [evaluatorBody, lensText, extraPrompt])
}
