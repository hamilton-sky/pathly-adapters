import { useState } from 'react'
import { Rows3 } from 'lucide-react'
import SkillSplitModal, { type ProposedCell } from '../../../shared/SkillSplitModal/SkillSplitModal'
import {
  composeSkillPrompt,
  headingLayers,
  type ComposedSegment,
} from '../../../../services/skillCompose'
import s from './StageSectionsButton.module.css'

interface Props {
  projectRoot: string
  /** The stage's skill (e.g. "development/build") — composed to list its sections. */
  skill: string
  /** Selected abilities — composed in so their sections appear as excludable too. */
  abilityIds: string[]
  /** Currently-excluded section headings (the saved selection). */
  excludedSections: string[]
  onChange: (headings: string[]) => void
}

// Per-stage section trim (#5): compose the stage's skill (+ its Pathly fragments + selected
// abilities), let the human UNCHECK ## sections to exclude, and persist the excluded HEADINGS
// (not trimmed text) so build_prompt drops them fresh at spawn. Fragments are locked in the
// split modal, so a stage trim can never drop platform glue (board CRUD / progress / completion).
export function StageSectionsButton({
  projectRoot,
  skill,
  abilityIds,
  excludedSections,
  onChange,
}: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [composed, setComposed] = useState<{
    prompt: string
    segments: ComposedSegment[]
  } | null>(null)

  async function openPicker(): Promise<void> {
    setLoading(true)
    const r = await composeSkillPrompt(skill, { projectRoot, abilityIds })
    setLoading(false)
    if (!r) return
    setComposed(r)
    setOpen(true)
  }

  const layers = composed ? headingLayers(composed.segments) : {}

  function handleConfirm(cells: ProposedCell[]): void {
    // Excluded = unchecked cells that aren't platform fragments (fragments are locked, so they
    // are always checked and never appear here — the filter is defence-in-depth).
    const excluded = cells
      .filter((c) => !c.checked && layers[c.heading] !== 'fragment')
      .map((c) => c.heading)
    onChange(excluded)
    setOpen(false)
  }

  return (
    <>
      <button
        type="button"
        className={s.btn}
        onClick={() => void openPicker()}
        disabled={loading}
        data-active={excludedSections.length > 0 ? 'true' : 'false'}
      >
        <Rows3 size={13} />
        {excludedSections.length > 0
          ? `Sections · ${excludedSections.length} excluded`
          : 'Configure sections'}
      </button>
      {open && composed && (
        <SkillSplitModal
          rawContent={composed.prompt}
          title="Exclude sections for this stage"
          subtitle="Uncheck sections to drop them from this stage's prompt on every run. Pathly fragments are locked. Saved as the selection — the prompt composes fresh at spawn, so an upstream edit never stale-seeds."
          confirmLabel="Save sections"
          hideInsertOne
          headingLayers={layers}
          initialUnchecked={excludedSections}
          onConfirm={handleConfirm}
          onInsertOne={() => setOpen(false)}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
