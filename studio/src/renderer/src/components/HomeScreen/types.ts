export interface PlanRow {
  name: string
  state: string
  flowType: 'team' | 'debug' | 'explore'
}

export type ProjectPlans = Record<string, PlanRow[]>
