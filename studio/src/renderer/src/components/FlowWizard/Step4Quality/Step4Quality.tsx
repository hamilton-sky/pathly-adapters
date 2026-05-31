import { useState } from 'react'
import type { Gate, Transition, TransitionRule, FeedbackRoute } from '../types'
import { Step5Gates } from '../Step5Gates/Step5Gates'
import { Step6FeedbackRouting } from '../Step6FeedbackRouting/Step6FeedbackRouting'
import { Step7TransitionRules } from '../Step7TransitionRules/Step7TransitionRules'
import styles from './Step4Quality.module.css'

interface Step4QualityProps {
  transitions: Transition[]
  gates: Record<string, Gate[]>
  feedbackRoutes: FeedbackRoute[]
  transitionRules: Record<string, TransitionRule>
  nonTerminalStates: string[]
  validStates: string[]
  onSetGates: (gates: Record<string, Gate[]>) => void
  onSetRoutes: (routes: FeedbackRoute[]) => void
  onSetRules: (rules: Record<string, TransitionRule>) => void
}

export function Step4Quality(props: Step4QualityProps): JSX.Element {
  type PanelKey = 'gates' | 'routing' | 'rules'
  const [open, setOpen] = useState<Record<PanelKey, boolean>>({
    gates: true,
    routing: false,
    rules: false
  })
  const gateCount = Object.values(props.gates).reduce((sum, items) => sum + items.length, 0)
  const routeCount = props.feedbackRoutes.filter((route) => route.tag.trim() && route.agent.trim()).length
  const ruleCount = Object.values(props.transitionRules).filter((rule) => rule.conditions.length > 0 || rule.default.trim()).length
  const panels: Array<[PanelKey, string, number, string]> = [
    ['gates', 'Gates', gateCount, `${gateCount} configured`],
    ['routing', 'Feedback routing', routeCount, `${routeCount} configured`],
    ['rules', 'Transition rules', ruleCount, `${ruleCount} rule${ruleCount === 1 ? '' : 's'}`],
  ]

  return (
    <div className={styles.root}>
      <div className={styles.title}>Quality &amp; routing</div>
      <div className={styles.sub}>Step 4 / 5 - Optional checks and routing rules.</div>

      {panels.map(([key, label, , countLabel]) => (
        <div key={key} className={styles.accordion}>
          <button
            type="button"
            className={styles.accordionBtn}
            onClick={() => setOpen((prev) => ({ ...prev, [key]: !prev[key] }))}
            {...(open[key] ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <span>{label}</span>
            <span className={styles.accordionMeta}>
              <span className={styles.accordionCount}>{countLabel}</span>
              <span className={styles.accordionChevron}>{open[key] ? '›' : '›'}</span>
            </span>
          </button>
          {open[key] && (
            <div className={styles.accordionPanel}>
              {key === 'gates' && (
                <Step5Gates
                  transitions={props.transitions}
                  gates={props.gates}
                  onSetGates={props.onSetGates}
                />
              )}
              {key === 'routing' && (
                <Step6FeedbackRouting
                  feedbackRoutes={props.feedbackRoutes}
                  onSetRoutes={props.onSetRoutes}
                />
              )}
              {key === 'rules' && (
                <Step7TransitionRules
                  nonTerminalStates={props.nonTerminalStates}
                  validStates={props.validStates}
                  transitionRules={props.transitionRules}
                  onSetRules={props.onSetRules}
                />
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
