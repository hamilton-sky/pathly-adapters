import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../store'
import { readFile, writeFile } from '../../services/pathlyApi'
import { useTheme } from '../../useTheme'
import type { Props, Transition, Gate, TransitionRule, FeedbackRoute } from './types'
import { makeStyles } from './FlowWizard.styles'
import { generateYaml } from './utils'
import { StepIndicator } from './StepIndicator/StepIndicator'
import { WizardFooter } from './WizardFooter/WizardFooter'
import { Step1Name } from './Step1Name/Step1Name'
import { Step2States } from './Step2States/Step2States'
import { Step3Transitions } from './Step3Transitions/Step3Transitions'
import { Step4Agents } from './Step4Agents/Step4Agents'
import { Step4Quality } from './Step4Quality/Step4Quality'
import { Step5Review } from './Step5Review/Step5Review'
import { Step0Entry } from './Step0Entry/Step0Entry'
import { YamlPreview } from './YamlPreview/YamlPreview'
import { WIZARD_TEMPLATES, type WizardTemplate } from './wizardTemplates'
import { DRAFT_FILE_NAME, parseDraft, serializeDraft, type WizardDraft } from './draftUtils'
import { validateStep } from './FlowWizard.validation'
import { FieldError } from '../ui'

const TOTAL_STEPS = 5

export function FlowWizard({ onClose, onCreated }: Props): JSX.Element {
  const { pathlyUserHome } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [step, setStep] = useState(0)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
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
  const [draftLoaded, setDraftLoaded] = useState(false)
  const [hasDraft, setHasDraft] = useState(false)
  const [savedDraft, setSavedDraft] = useState<WizardDraft | null>(null)

  const validStates = states.filter((s) => s.trim())
  const nonTerminalStates = validStates.slice(0, -1)
  const terminalState = validStates[validStates.length - 1] ?? ''

  const yamlPreview = useMemo(
    () => generateYaml(flowName || 'my-flow', storagePath, validStates, agentMap, transitions, gates, feedbackRoutes, transitionRules),
    [flowName, storagePath, validStates, agentMap, transitions, gates, feedbackRoutes, transitionRules]
  )

  const draftPath = pathlyUserHome ? `${pathlyUserHome}/flows/${DRAFT_FILE_NAME}` : ''

  useEffect(() => {
    let cancelled = false
    async function loadDraft(): Promise<void> {
      if (!draftPath) return
      try {
        const content = await readFile(draftPath)
        const draft = parseDraft(content)
        if (!draft || cancelled) {
          setHasDraft(false)
          setSavedDraft(null)
          setDraftLoaded(true)
          return
        }
        setSavedDraft(draft)
        setHasDraft(true)
      } catch {
        setHasDraft(false)
      } finally {
        if (!cancelled) setDraftLoaded(true)
      }
    }
    void loadDraft()
    return () => { cancelled = true }
  }, [draftPath])

  useEffect(() => {
    if (!draftLoaded || !draftPath || step === 0) return
    const draft: WizardDraft = {
      version: 1,
      flowName,
      description,
      step,
      selectedTemplateId,
      states,
      transitions,
      agentMap,
      gates,
      feedbackRoutes,
      transitionRules,
      storagePath
    }
    void writeFile(draftPath, serializeDraft(draft)).then(() => setHasDraft(true)).catch(() => {})
  }, [draftLoaded, draftPath, flowName, description, step, selectedTemplateId, states, transitions, agentMap, gates, feedbackRoutes, transitionRules, storagePath])

  function applyTemplate(template: WizardTemplate | null): void {
    if (!template) return
    setSelectedTemplateId(template.id)
    setStates(template.states)
    setTransitions([])
    setStep(1)
  }

  function applyDraft(draft: WizardDraft): void {
    setFlowName(draft.flowName)
    setDescription(draft.description)
    setStep(draft.step)
    setSelectedTemplateId(draft.selectedTemplateId)
    setStates(draft.states)
    setTransitions(draft.transitions)
    setAgentMap(draft.agentMap)
    setGates(draft.gates)
    setFeedbackRoutes(draft.feedbackRoutes)
    setTransitionRules(draft.transitionRules)
    setStoragePath(draft.storagePath)
  }

  function resumeDraft(): void {
    if (!savedDraft) return
    applyDraft(savedDraft)
    setStep(savedDraft.step)
  }

  function startBlank(): void {
    setSelectedTemplateId('blank')
    setStates(['DONE'])
    setTransitions([])
    setAgentMap({})
    setGates({})
    setFeedbackRoutes([])
    setTransitionRules({})
    setStep(1)
  }

  function goToStep(next: number): void {
    if (next < 0) return
    if (next > TOTAL_STEPS) return
    if (next === 2 && step === 1 && transitions.length === 0 && validStates.length > 1) {
      const autoTransitions: Transition[] = []
      for (let i = 0; i < validStates.length - 1; i++) {
        autoTransitions.push({ from: validStates[i], to: validStates[i + 1], label: 'default' })
      }
      setTransitions(autoTransitions)
    }
    setStep(next)
  }

  function handleNext(): void {
    if (step === 0) return
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
    setStep((s) => Math.max(0, s - 1))
  }

  function jumpToStep(next: number): void {
    if (next >= 1 && next <= step) setStep(next)
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

  function reorderState(from: number, to: number): void {
    setStates((prev) => {
      if (from === to) return prev
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return next
    })
    setTransitions([])
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
    if (!pathlyUserHome) {
      setSaveError('User library path is not available')
      return
    }
    const trimmedName = flowName.trim()
    const filePath = `${pathlyUserHome}/flows/${trimmedName}.flow.yaml`
    setSaving(true)
    try {
      await writeFile(filePath, yamlPreview)
      if (draftPath) {
        await writeFile(draftPath, '')
      }
      onCreated(filePath)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const nextDisabled = touched[step] && Object.keys(stepErrors[step] ?? {}).length > 0

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.card}>
        {step > 0 && (
          <>
            <span style={styles.stepCounter}>Step {step} of {TOTAL_STEPS}</span>
            <div style={styles.progressBarWrap}>
              <div style={{ ...styles.progressBar, width: `${(step / TOTAL_STEPS) * 100}%` }} />
            </div>
            <StepIndicator step={step} totalSteps={TOTAL_STEPS} onJumpToStep={jumpToStep} t={t} styles={styles} />
          </>
        )}

        <div style={step === 0 ? styles.contentFull : styles.content}>
          <div>
            {step === 0 && (
                <Step0Entry
                  selectedTemplateId={selectedTemplateId}
                  templates={WIZARD_TEMPLATES}
                  onSelectTemplate={applyTemplate}
                  onStartBlank={startBlank}
                  onResume={resumeDraft}
                  hasDraft={hasDraft}
                />
              )}
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
                  onReorderState={reorderState}
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
              />
            )}
            {step === 5 && (
              <>
                <Step4Quality
                  transitions={transitions.filter((tr) => tr.from.trim() && tr.to.trim())}
                  gates={gates}
                  feedbackRoutes={feedbackRoutes}
                  transitionRules={transitionRules}
                  nonTerminalStates={nonTerminalStates}
                  validStates={validStates}
                  onSetGates={setGates}
                  onSetRoutes={setFeedbackRoutes}
                  onSetRules={setTransitionRules}
                  styles={styles}
                />
                <Step5Review
                  yamlPreview={yamlPreview}
                  storagePath={storagePath}
                  onStoragePathChange={setStoragePath}
                  error={saveError}
                  styles={styles}
                />
              </>
            )}
          </div>

          {step > 0 && (
            <aside style={styles.sidebar}>
              <YamlPreview yaml={yamlPreview} styles={styles} />
            </aside>
          )}
        </div>

        <WizardFooter
          step={step}
          totalSteps={TOTAL_STEPS}
          onCancel={onClose}
          onBack={handleBack}
          onNext={handleNext}
          onSave={handleSave}
          saving={saving}
          nextDisabled={nextDisabled}
        />
      </div>
    </div>
  )
}
