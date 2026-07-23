// Local view-model types for the Skill Composition kit.
import type { ComposedSection } from './integration'

export type SkillSource = 'manifest' | 'override'
export type PanelView = 'preview' | 'config'
export type ConfigLayout = 'table' | 'split'
export type PreviewTab = 'fragments' | 'abilities' | 'system'

/** One included fragment, enriched with curated meta for display. */
export interface FragmentVM {
  order: number
  name: string
  purpose: string
  tokens: number
}

/** A row in the tabbed preview list (fragment / ability / system-prompt segment). */
export interface PreviewRowVM {
  id: string
  kind: 'frag' | 'ability' | 'system'
  label: string
  on: boolean
  hasCheck: boolean
  trail: string
  fragment: string | null
}

/** What the inspect drawer shows. */
export interface DrawerTarget {
  kind: 'frag' | 'ability' | 'system'
  id: string
}

export interface DrawerDetail {
  title: string
  kindLabel: string
  desc: string
  tokens: number
  source: string
  on: boolean
  canToggle: boolean
  fragment: string | null
}

export type { ComposedSection }
