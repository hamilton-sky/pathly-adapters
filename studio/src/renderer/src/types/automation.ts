export type AutomationStepStatus = 'pending' | 'approved' | 'skipped' | 'done' | 'error'

export interface AutomationStep {
  id: string
  description: string
  action: {
    type: 'click' | 'fill' | 'select' | 'navigate'
    label: string
    value?: string
    screen?: string
  }
  status: AutomationStepStatus
  errorMessage?: string
}
