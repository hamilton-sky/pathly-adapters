export interface StepErrors {
  [field: string]: string
}

export function validateStep(
  step: number,
  values: {
    flowName: string
    states: string[]
    transitions: { from: string; to: string; label: string }[]
    agentMap: Record<string, string>
  }
): StepErrors {
  const errors: StepErrors = {}
  if (step === 1) {
    if (!values.flowName.trim()) errors.name = 'Flow name is required'
    else if (!/^[a-zA-Z0-9-_]+$/.test(values.flowName.trim()))
      errors.name = 'Only letters, numbers, hyphens, and underscores'
  }
  if (step === 2) {
    const nonEmpty = values.states.filter((s) => s.trim())
    if (nonEmpty.length < 1) errors.states = 'At least one state is required'
  }
  // Steps 3, 4, 5: always valid (optional or read-only)
  return errors
}
