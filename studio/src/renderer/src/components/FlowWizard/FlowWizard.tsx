import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { writeFile } from '../../services/pathlyApi'
import { useTheme } from '../../useTheme'
import type { Props, Transition } from './types'
import { makeStyles } from './FlowWizard.styles'
import { generateYaml } from './utils'
import { StepIndicator } from './StepIndicator'
import { WizardFooter } from './WizardFooter'
import { Step1Name } from './Step1Name'
import { Step2States } from './Step2States'
import { Step3Transitions } from './Step3Transitions'
import { Step4Agents } from './Step4Agents'
import { Step5Review } from './Step5Review'

export function FlowWizard({ onClose, onCreated }: Props): JSX.Element {
  const { projectPath } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [step, setStep] = useState(1)
  const [flowName, setFlowName] = useState('')
  const [description, setDescription] = useState('')
  const [states, setStates] = useState(['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'DONE'])
  const [transitions, setTransitions] = useState<Transition[]>([])
  const [agentMap, setAgentMap] = useState<Record<string, string>>({})
  const [storagePath, setStoragePath] = useState('pathly/plans/{topic}/')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  function goToStep(next: number): void {
    if (next === 3 && step === 2) {
      const autoTransitions: Transition[] = []
      for (let i = 0; i < states.length - 1; i++) {
        autoTransitions.push({ from: states[i], to: states[i + 1], label: 'default' })
      }
      if (transitions.length === 0) {
        setTransitions(autoTransitions)
      }
    }
    setError(null)
    setStep(next)
  }

  function handleNext(): void {
    if (step === 1) {
      if (!flowName.trim()) {
        setError('Flow name is required')
        return
      }
      if (!/^[a-zA-Z0-9-_]+$/.test(flowName.trim())) {
        setError('Flow name must be alphanumeric with hyphens or underscores')
        return
      }
    }
    if (step === 2) {
      const nonEmpty = states.filter((s) => s.trim())
      if (nonEmpty.length < 2) {
        setError('At least 2 states required')
        return
      }
    }
    goToStep(step + 1)
  }

  function handleBack(): void {
    setError(null)
    setStep((s) => s - 1)
  }

  function updateState(idx: number, value: string): void {
    const next = [...states]
    next[idx] = value.toUpperCase()
    setStates(next)
  }

  function removeState(idx: number): void {
    if (states.length <= 2) return
    setStates((s) => s.filter((_, i) => i !== idx))
  }

  function addState(): void {
    setStates((s) => [...s, ''])
  }

  function updateTransition(idx: number, patch: Partial<Transition>): void {
    setTransitions((prev) => prev.map((tr, i) => (i === idx ? { ...tr, ...patch } : tr)))
  }

  function removeTransition(idx: number): void {
    setTransitions((prev) => prev.filter((_, i) => i !== idx))
  }

  function addTransition(): void {
    setTransitions((prev) => [...prev, { from: states[0] ?? '', to: states[1] ?? '', label: 'default' }])
  }

  function updateAgent(state: string, value: string): void {
    setAgentMap((prev) => ({ ...prev, [state]: value }))
  }

  async function handleSave(): Promise<void> {
    if (!projectPath) return
    const trimmedName = flowName.trim()
    const yaml = generateYaml(trimmedName, storagePath, states.filter((s) => s.trim()), agentMap, transitions)
    const filePath = `${projectPath}/src/pathly_data/core/flows/${trimmedName}.flow.yaml`
    setSaving(true)
    try {
      await writeFile(filePath, yaml)
      onCreated(filePath)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const nonTerminalStates = states.slice(0, -1)
  const terminalState = states[states.length - 1]
  const validStates = states.filter((s) => s.trim())

  const yamlPreview = generateYaml(
    flowName || 'my-flow',
    storagePath,
    validStates,
    agentMap,
    transitions
  )

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.card}>
        <StepIndicator step={step} t={t} styles={styles} />

        <div style={styles.content}>
          {step === 1 && (
            <Step1Name
              flowName={flowName}
              description={description}
              onFlowNameChange={setFlowName}
              onDescriptionChange={setDescription}
              error={error}
              styles={styles}
            />
          )}
          {step === 2 && (
            <Step2States
              states={states}
              onUpdateState={updateState}
              onRemoveState={removeState}
              onAddState={addState}
              error={error}
              styles={styles}
            />
          )}
          {step === 3 && (
            <Step3Transitions
              transitions={transitions}
              validStates={validStates}
              onUpdateTransition={updateTransition}
              onRemoveTransition={removeTransition}
              onAddTransition={addTransition}
              states={states}
              styles={styles}
            />
          )}
          {step === 4 && (
            <Step4Agents
              nonTerminalStates={nonTerminalStates}
              terminalState={terminalState}
              agentMap={agentMap}
              onUpdateAgent={updateAgent}
              styles={styles}
            />
          )}
          {step === 5 && (
            <Step5Review
              yamlPreview={yamlPreview}
              storagePath={storagePath}
              onStoragePathChange={setStoragePath}
              error={error}
              styles={styles}
            />
          )}
        </div>

        <WizardFooter
          step={step}
          onCancel={onClose}
          onBack={handleBack}
          onNext={handleNext}
          onSave={handleSave}
          saving={saving}
          styles={styles}
        />
      </div>
    </div>
  )
}
