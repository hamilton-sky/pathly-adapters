/*
 * SINGLE WIRING POINT.
 * This kit talks to Pathly only through this file. When you drop the folder into
 * studio/src/renderer/src/components, fix the two import paths below to match your
 * tree (they assume components/SkillCompositionKit/ sitting beside services/ and store/).
 * Nothing else in the kit imports Pathly directly.
 */
export type {
  SkillCompositionCatalog,
  SkillCompositionEntry,
  ComposedSection,
} from '../../services/skillComposition'

export {
  fetchSkillComposition,
  previewComposedSkill,
  saveSkillCompositionOverride,
  resetSkillComposition,
} from '../../services/skillComposition'

import { useProjectStore } from '../../store/projectStore'

/** The active project root the panel operates on. */
export function useProjectPath(): string {
  return useProjectStore((s) => s.projectPath)
}
