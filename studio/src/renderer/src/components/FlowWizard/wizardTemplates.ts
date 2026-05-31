export interface WizardTemplate {
  id: string
  name: string
  description: string
  states: string[]
}

export const WIZARD_TEMPLATES: WizardTemplate[] = [
  {
    id: 'standard-pipeline',
    name: 'Standard pipeline',
    description: 'STORMING → PLANNING → BUILDING → REVIEWING → TESTING → DONE',
    states: ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'DONE']
  },
  {
    id: 'review-loop',
    name: 'Review loop',
    description: 'DRAFTING → REVIEWING → DONE',
    states: ['DRAFTING', 'REVIEWING', 'DONE']
  },
  {
    id: 'debug-cycle',
    name: 'Debug cycle',
    description: 'REPRODUCING → DIAGNOSING → FIXING → TESTING → DONE',
    states: ['REPRODUCING', 'DIAGNOSING', 'FIXING', 'TESTING', 'DONE']
  },
  {
    id: 'blank',
    name: 'Blank',
    description: 'Start with a single DONE state and build everything yourself.',
    states: ['DONE']
  }
]
