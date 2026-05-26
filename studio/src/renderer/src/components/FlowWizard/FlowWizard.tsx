import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { writeFile } from '../../services/pathlyApi'
import { useTheme } from '../../useTheme'
import type { Props, Transition, Gate, TransitionRule, FeedbackRoute } from './types'
import { makeStyles } from './FlowWizard.styles'
import { generateYaml } from './utils'
import { StepIndicator } from './StepIndicator'
import { WizardFooter } from './WizardFooter'
import { Step1Name } from './Step1Name'
import { Step2States } from './Step2States'
import { Step3Transitions } from './Step3Transitions'
import { Step4Agents } from './Step4Agents'
import { Step5Gates } from './Step5Gates'
import { Step6FeedbackRouting } from './Step6FeedbackRouting'
import { Step7TransitionRules } from './Step7TransitionRules'
import { Step5Review } from './Step5Review'
import { validateStep } from './FlowWizard.validation'
import { FieldError } from '../ui'

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
  const [gates, setGates] = useState<Record<string, Gate[]>>({})
  const [feedbackRoutes, setFeedbackRoutes] = useState<FeedbackRoute[]>([
    { tag: 'HUMAN_QUESTIONS', agent: 'human' },
    { tag: 'BLOCKED_ON_HUMAN', agent: 'human' },
    { tag: 'ARCH_FEEDBACK', agent: 'architect' },
    { tag: 'REVIEW_FAILURES', agent: 'builder' },
    { tag: 'TEST_FAILURES', agent: 'builder' },
  ])
  const [transitionRules, setTransitionRules] = useState<Record<string, TransitionRule>>({})
  const [storagePath, setStoragePath] = useState('pathly/plans/{topic}/')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [stepErrors, setStepErrors] = useState<Record<number, Record<string, string>>>({})
  const [touched, setTouched] = useState<Record<number, boolean>>({})

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    if (touched[1]) {
      const errors = validateStep(1, { flowName, states, transitions, agentMap })
      setStepErrors((prev) => ({ ...prev, 1: errors }))
    }
  }, [flowName])

  useEffect(() => {
    if (touched[2]) {
      const errors = validateStep(2, { flowName, states, transitions, agentMap })
      setStepErrors((prev) => ({ ...prev, 2: errors }))
    }
  }, [states])

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
    setStep(next)
  }

  function handleNext(): void {
    const values = { flowName, states, transitions, agentMap }
    const errors = validateStep(step, values)
    if (Object.keys(errors).length > 0) {
      setStepErrors((prev) => ({ ...prev, [step]: errors }))
      setTouched((prev) => ({ ...prev, [step]: true }))
      return
    }
    setTouched((prev) => ({ ...prev, [step]: true }))
    goToStep(step + 1)
  }

  function handleBack(): void {
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
    const yaml = generateYaml(trimmedName, storagePath, states.filter((s) => s.trim()), agentMap, transitions, gates, feedbackRoutes, transitionRules)
    const filePath = `${projectPath}/src/pathly_data/core/flows/${trimmedName}.flow.yaml`
    setSaving(true)
    try {
      await writeFile(filePath, yaml)
      onCreated(filePath)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
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
    transitions,
    gates,
    feedbackRoutes,
    transitionRules
  )

  const nextDisabled = touched[step] && Object.keys(stepErrors[step] ?? {}).length > 0

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.card}>
        <span style={styles.stepCounter}>
          Step {step} of 8
        </span>
        <StepIndicator step={step} t={t} styles={styles} />

        <div style={styles.content}>
          {step === 1 && (
            <>
              <Step1Name
                flowName={flowName}
                description={description}
                onFlowNameChange={setFlowName}
                onDescriptionChange={setDescription}
                styles={styles}
              />
              <FieldError message={stepErrors[1]?.name} />
            </>
          )}
          {step === 2 && (
            <>
              <Step2States
                states={states}
                onUpdateState={updateState}
                onRemoveState={removeState}
                onAddState={addState}
                styles={styles}
              />
              <FieldError message={stepErrors[2]?.states} />
            </>
          )}
          {step === 3 && (
            <Step3Transitions
              transitions={transitions}
              validStates={validStates}
              onUpdateTransition={updateTransition}
              onRemoveTransition={removeTransition}
              onAddTransition={addTransition}
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
            <Step5Gates
              transitions={transitions.filter((tr) => tr.from.trim() && tr.to.trim())}
              gates={gates}
              onSetGates={setGates}
              styles={styles}
            />
          )}
          {step === 6 && (
            <Step6FeedbackRouting
              feedbackRoutes={feedbackRoutes}
              onSetRoutes={setFeedbackRoutes}
              styles={styles}
            />
          )}
          {step === 7 && (
            <Step7TransitionRules
              nonTerminalStates={nonTerminalStates.filter((s) => s.trim())}
              validStates={states.filter((s) => s.trim())}
              transitionRules={transitionRules}
              onSetRules={setTransitionRules}
              styles={styles}
            />
          )}
          {step === 8 && (
            <Step5Review
              yamlPreview={yamlPreview}
              storagePath={storagePath}
              onStoragePathChange={setStoragePath}
              error={saveError}
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
          nextDisabled={nextDisabled}
          styles={styles}
        />
      </div>
    </div>
  )
}
