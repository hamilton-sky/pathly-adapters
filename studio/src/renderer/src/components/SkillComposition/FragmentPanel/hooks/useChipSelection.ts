import { useState } from 'react'
import { BODY_CHIP_ID } from '../../chipIds'

interface UseChipSelectionResult {
  activeChipId: string
  selectChip: (id: string) => void
}

/** UI state: which chip (skill body / a fragment / full composed) is selected for viewing. */
export function useChipSelection(): UseChipSelectionResult {
  const [activeChipId, setActiveChipId] = useState<string>(BODY_CHIP_ID)
  return { activeChipId, selectChip: setActiveChipId }
}
