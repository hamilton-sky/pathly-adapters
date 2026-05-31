import React, { useState } from 'react'
import type { Gate, Transition, TransitionRule, FeedbackRoute } from '../types'
import { Step5Gates } from '../Step5Gates/Step5Gates'
import { Step6FeedbackRouting } from '../Step6FeedbackRouting/Step6FeedbackRouting'
import { Step7TransitionRules } from '../Step7TransitionRules/Step7TransitionRules'

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
  styles: Record<string, React.CSSProperties>
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
  const panels: Array<[PanelKey, string]> = [
    ['gates', 'Gates'],
    ['routing', 'Feedback routing'],
    ['rules', 'Transition rules']
  ]

  return (
    <div>
      <div style={props.styles.stepHeader}>Quality &amp; routing</div>
      <div style={props.styles.stepSub}>Step 4 / 5 - Optional checks and routing rules.</div>

      {panels.map(([key, label]) => (
        <div key={key} style={props.styles.accordion}>
          <button
            style={props.styles.accordionButton}
            onClick={() => setOpen((prev) => ({ ...prev, [key]: !prev[key] }))}
          >
            <span>{label}</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: props.styles.stepSub.color }}>
                {key === 'gates' ? `${gateCount} configured` : key === 'routing' ? `${routeCount} configured` : `${ruleCount} rule${ruleCount === 1 ? '' : 's'}`}
              </span>
              <span style={{ color: props.styles.stepSub.color }}>{open[key] ? '›' : '›'}</span>
            </span>
          </button>
          {open[key] && (
            <div style={props.styles.accordionPanel}>
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
                  styles={props.styles}
                />
              )}
              {key === 'rules' && (
                <Step7TransitionRules
                  nonTerminalStates={props.nonTerminalStates}
                  validStates={props.validStates}
                  transitionRules={props.transitionRules}
                  onSetRules={props.onSetRules}
                  styles={props.styles}
                />
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
