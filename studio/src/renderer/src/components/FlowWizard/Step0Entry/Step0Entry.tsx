import React from 'react'
import type { WizardTemplate } from '../wizardTemplates'
import styles from './Step0Entry.module.css'

interface Step0EntryProps {
  selectedTemplateId: string | null
  templates: WizardTemplate[]
  onSelectTemplate: (template: WizardTemplate | null) => void
  onStartBlank: () => void
  onResume?: () => void
  hasDraft?: boolean
}

export function Step0Entry({
  selectedTemplateId,
  templates,
  onSelectTemplate,
  onStartBlank,
  onResume,
  hasDraft,
}: Step0EntryProps): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.title}>New flow</div>
      <div className={styles.sub}>Choose a template, start blank, or resume a draft.</div>

      <div className={styles.choiceGrid}>
        <button
          className={`${styles.choiceCard} ${selectedTemplateId === (templates[0]?.id ?? null) ? styles.choiceCardActive : ''}`}
          onClick={() => onSelectTemplate(templates[0] ?? null)}
        >
          <div className={styles.choiceTitle}>From template</div>
          <div className={styles.choiceCopy}>Pre-filled stages for common workflows</div>
        </button>
        <button
          className={styles.choiceCard}
          onClick={onStartBlank}
        >
          <div className={styles.choiceTitle}>Start blank</div>
          <div className={styles.choiceCopy}>Define every stage yourself</div>
        </button>
      </div>

      <div className={styles.sectionLabel}>Choose a template</div>
      <div className={styles.templateList}>
        {templates.map((template) => {
          const active = selectedTemplateId === template.id
          return (
            <button
              key={template.id}
              className={`${styles.templateCard} ${active ? styles.templateCardActive : ''}`}
              onClick={() => onSelectTemplate(template)}
            >
              <div className={styles.templateRow}>
                <strong>{template.name}</strong>
                {active && <span className={styles.selected}>selected</span>}
              </div>
              <div className={styles.templateDesc}>{template.description}</div>
            </button>
          )
        })}
      </div>

      {hasDraft && onResume && (
        <div className={styles.resumeCard}>
          <div className={styles.resumeLabel}>Resume draft</div>
          <button className={styles.addBtn} onClick={onResume}>Resume saved draft</button>
        </div>
      )}
    </div>
  )
}
