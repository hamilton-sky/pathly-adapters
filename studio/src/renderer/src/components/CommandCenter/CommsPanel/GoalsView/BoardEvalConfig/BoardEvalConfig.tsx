import { ArrowRight } from 'lucide-react'
import { type EditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import { PromptBanner, usePromptContent } from '../../../../shared/PromptPreview/PromptPreview'
import { PromptActionConfig } from '../../../../shared/PromptActionConfig/PromptActionConfig'
import { useMergedPresets } from '../../../../shared/PromptActionConfig/useMergedPresets'
import { AbilityToggles } from '../../../../shared/AbilityToggles/AbilityToggles'
import type { Ability } from '../../../../../services/abilities'
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
  /** Selected layer-3 ability ids composed into the evaluator prompt. */
  abilityIds: string[]
  onAbilitiesChange: (rows: Ability[]) => void
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
  selectedLens, lensText, extraPrompt, selectedCli, running, abilityIds, onAbilitiesChange,
  onSelectLens, onLensTextChange, onExtraPromptChange, onCliChange, onReset, onRun, onClose,
}: Props): JSX.Element {
  const projectPath = useStore((st) => st.projectPath)
  const setMdEditorPath = useUiStore((st) => st.setMdEditorPath)
  const setActivePanel = useUiStore((st) => st.setActivePanel)
  const skillCatalog = useSkillCatalog(projectPath)

  // Merge the built-in lenses with the user's DB-backed 'eval' library prompts.
  const { presets: mergedLenses, addPreset } = useMergedPresets(EVAL_LENSES, {
    kind: 'preset',
    category: 'eval',
    projectRoot: projectPath,
  })

  // A DB lens carries a prompt too → not the default → show the editable banner, not the skill preview.
  const lensPrompt = mergedLenses.find((l) => l.name === selectedLens)?.prompt ?? ''
  const isDefaultLens = !lensPrompt

  function handleSelectLens(name: string): void {
    onSelectLens(name)
    // A DB lens isn't in EVAL_LENSES, so the parent's pickLens can't resolve its body — load it here.
    const dbLens = mergedLenses.find((l) => l.name === name)
    if (dbLens && !EVAL_LENSES.some((l) => l.name === name)) onLensTextChange(dbLens.prompt)
  }

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
      presets={mergedLenses}
      selectedPreset={selectedLens}
      promptText={lensText}
      extra={extraPrompt}
      cli={selectedCli}
      running={running}
      primaryLabel="Run now"
      onSelectPreset={handleSelectLens}
      onPromptTextChange={onLensTextChange}
      onExtraChange={onExtraPromptChange}
      onCliChange={onCliChange}
      onReset={onReset}
      onPrimary={onRun}
      onAddPreset={lensText.trim() ? (name) => addPreset(name, lensText) : undefined}
      bannerSlot={bannerSlot}
      abilitiesSlot={
        <AbilityToggles projectRoot={projectPath} selectedIds={abilityIds} onChange={onAbilitiesChange} />
      }
      footerNote={footerNote}
    />
  )
}
