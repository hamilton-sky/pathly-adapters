import React from 'react'
import type { WizardTemplate } from './wizardTemplates'

interface Step0EntryProps {
  selectedTemplateId: string | null
  templates: WizardTemplate[]
  onSelectTemplate: (template: WizardTemplate | null) => void
  onStartBlank: () => void
  onResume?: () => void
  hasDraft?: boolean
  styles: Record<string, React.CSSProperties>
}

export function Step0Entry({
  selectedTemplateId,
  templates,
  onSelectTemplate,
  onStartBlank,
  onResume,
  hasDraft,
  styles
}: Step0EntryProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>New flow</div>
      <div style={styles.stepSub}>Choose a template, start blank, or resume a draft.</div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px', marginBottom: '18px' }}>
        <button style={{ ...styles.templateCard, ...styles.templateCardActive }} onClick={() => onSelectTemplate(templates[0] ?? null)}>
          <div style={{ fontWeight: 700, marginBottom: '4px' }}>From template</div>
          <div style={{ color: styles.stepSub.color }}>Pre-filled stages for common workflows</div>
        </button>
        <button style={{ ...styles.templateCard }} onClick={onStartBlank}>
          <div style={{ fontWeight: 700, marginBottom: '4px' }}>Start blank</div>
          <div style={{ color: styles.stepSub.color }}>Define every stage yourself</div>
        </button>
      </div>

      <div style={{ marginBottom: '10px', color: styles.stepSub.color, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Choose a template
      </div>
      <div style={{ display: 'grid', gap: '10px' }}>
        {templates.map((template) => {
          const active = selectedTemplateId === template.id
          return (
            <button
              key={template.id}
              style={{
                ...styles.templateCard,
                ...(active ? styles.templateCardActive : {})
              }}
              onClick={() => onSelectTemplate(template)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <strong>{template.name}</strong>
                {active && <span style={{ color: styles.stepSub.color }}>selected</span>}
              </div>
              <div style={{ color: styles.stepSub.color, marginTop: '6px', fontFamily: 'monospace', fontSize: '12px', lineHeight: 1.5 }}>
                {template.description}
              </div>
            </button>
          )
        })}
      </div>

      {hasDraft && onResume && (
        <div style={{ ...styles.summaryCard, marginTop: '16px' }}>
          <div style={{ fontWeight: 700, marginBottom: '4px' }}>Resume draft</div>
          <button style={styles.addBtn} onClick={onResume}>Resume saved draft</button>
        </div>
      )}
    </div>
  )
}
