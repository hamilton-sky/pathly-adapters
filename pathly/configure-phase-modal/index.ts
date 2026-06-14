/* Public surface of the Configure-phase component family.
   Import the whole modal, or cherry-pick the reusable primitives. */

export { ConfigurePhaseModal } from './ConfigurePhaseModal'

// Reusable primitives
export { Modal } from './components/Modal/Modal'
export { StatePill } from './components/StatePill/StatePill'
export { SectionLabel } from './components/SectionLabel/SectionLabel'
export { Chip } from './components/Chip/Chip'
export { AddChip } from './components/AddChip/AddChip'
export { ChipGroup } from './components/ChipGroup/ChipGroup'
export { SegmentedControl } from './components/SegmentedControl/SegmentedControl'
export { IconButton } from './components/IconButton/IconButton'
export { Button } from './components/Button/Button'

// Domain components
export { AssemblyRecipe } from './components/AssemblyRecipe/AssemblyRecipe'
export { PromptPreview } from './components/PromptPreview/PromptPreview'

// Types & data
export type { StageName, ChipVariant, PhaseConfig } from './types'
export {
  CLI_HOSTS,
  AGENTS,
  SKILLS,
  STAGE_DEFAULTS,
  SKILL_PROMPTS,
} from './configurePhaseModalData'
