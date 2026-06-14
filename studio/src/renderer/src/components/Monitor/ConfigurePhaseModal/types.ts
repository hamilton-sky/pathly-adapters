/* Shared types for the Configure-phase component family. */

export type StageName =
  | 'STORMING'
  | 'PLANNING'
  | 'BUILDING'
  | 'REVIEWING'
  | 'TESTING'
  | 'DONE'

/** Which selection group a chip belongs to — drives its accent colour. */
export type ChipVariant = 'host' | 'agent' | 'skill'

/** The three things a phase assembles into a prompt. */
export interface PhaseConfig {
  host: string
  agent: string
  skill: string
}
