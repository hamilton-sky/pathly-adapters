import { ArrowRight } from 'lucide-react'
import { type EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import { PromptBanner, usePromptContent } from '../../../../shared/PromptPreview/PromptPreview'
import { PromptActionConfig } from '../../../../shared/PromptActionConfig/PromptActionConfig'
import { useSkillCatalog } from '../../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import { useStore } from '../../../../../store'
import { useUiStore } from '../../../../../store/uiStore'
import { EVAL_LENSES } from '../../SingleAgentButton/agentFormData'
import s from './BoardEvalConfig.module.css'

const EVAL_SKILL_REL = 'planning/evaluate'

interface Props {
  selectedLens: string
  lensText: string
  extraPrompt: string
  selectedCli: EditorCli
  running: boolean
  onSelectLens: (name: string) => void
  onLensTextChange: (v: string) => void
  onExtraPromptChange: (v: string) => void
  onCliChange: (cli: EditorCli) => void
  onReset: () => void
  onRun: () => void
  onClose: () => void
}

// The whole-board path of the evaluator popover: lens preset + extra instructions + engine,
// with a live preview banner of the built-in evaluate skill (openable in the editor). Shown
// when the Evaluate target is the whole board rather than a specific goal.
export function BoardEvalConfig({
  selectedLens, lensText, extraPrompt, selectedCli, running,
  onSelectLens, onLensTextChange, onExtraPromptChange, onCliChange, onReset, onRun, onClose,
}: Props): JSX.Element {
  const projectPath = useStore((st) => st.projectPath)
  const setMdEditorPath = useUiStore((st) => st.setMdEditorPath)
  const setActivePanel = useUiStore((st) => st.setActivePanel)
  const skillCatalog = useSkillCatalog(projectPath)

  const lensPrompt = EVAL_LENSES.find((l) => l.name === selectedLens)?.prompt ?? ''
  const isDefaultLens = !lensPrompt

  const evaluateContent = usePromptContent(
    isDefaultLens ? EVAL_SKILL_REL : '',
    'src/pathly_data/core/skills', skillCatalog,
    { [EVAL_SKILL_REL]: EVAL_SKILL_REL }, {}, projectPath,
  )
  const evaluateMdPath = projectPath ? `${projectPath}/src/pathly_data/core/skills/${EVAL_SKILL_REL}.md` : null

  function openEvaluateSkill(): void {
    if (!evaluateMdPath) return
    setMdEditorPath(evaluateMdPath)
    setActivePanel('markdown-editor')
    onClose()
  }

  const footerNote = (
    <>
      <ArrowRight size={12} className={s.redirectIcon} />
      Need an agent or skill? Use <strong>Run on this board</strong>
    </>
  )

  const bannerSlot = isDefaultLens ? (
    <PromptBanner
      content={evaluateContent}
      mdEditorPath={evaluateMdPath}
      onOpenMdEditor={openEvaluateSkill}
    />
  ) : undefined

  return (
    <PromptActionConfig
      heading="Configure evaluator"
      presetLabel="LENS"
      presets={EVAL_LENSES}
      selectedPreset={selectedLens}
      promptText={lensText}
      extra={extraPrompt}
      cli={selectedCli}
      running={running}
      primaryLabel="Run now"
      onSelectPreset={onSelectLens}
      onPromptTextChange={onLensTextChange}
      onExtraChange={onExtraPromptChange}
      onCliChange={onCliChange}
      onReset={onReset}
      onPrimary={onRun}
      bannerSlot={bannerSlot}
      footerNote={footerNote}
    />
  )
}
