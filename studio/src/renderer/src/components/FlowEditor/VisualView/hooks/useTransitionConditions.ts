import { useState } from 'react'
import type { FlowYaml } from '../../../../types'

export interface StateRule {
  default?: string
  on_artifact?: Record<string, string>
  on_content?: Array<{ file?: string; contains?: string; regex?: string; next: string }>
  decide?: { question?: string; options?: Record<string, string>; default?: string }
}

export type ConditionType = 'default' | 'on_artifact' | 'on_content' | 'decide'

export interface AddConditionState {
  open: boolean
  type: ConditionType
  artifact: string
  file: string
  contains: string
  question: string
  optionLabel: string
}

interface UseTransitionConditionsResult {
  addCond: AddConditionState
  setAddCond: React.Dispatch<React.SetStateAction<AddConditionState>>
  submitAddCondition: () => void
  removeDefault: () => void
  removeArtifactEntry: (artifactName: string) => void
  removeContentEntry: (idx: number) => void
  removeDecide: () => void
}

export function useTransitionConditions(
  source: string,
  target: string,
  data: FlowYaml,
  onDataChange: ((updated: FlowYaml) => void) | undefined,
): UseTransitionConditionsResult {
  const rules = (data.transition_rules as Record<string, StateRule> | undefined) ?? {}
  const sourceRule: StateRule = rules[source] ?? {}

  const [addCond, setAddCond] = useState<AddConditionState>({
    open: false, type: 'default', artifact: '', file: '', contains: '', question: '', optionLabel: 'approve',
  })

  function updateRule(updated: StateRule): void {
    if (!onDataChange) return
    const newRules = { ...rules, [source]: updated }
    onDataChange({ ...data, transition_rules: newRules })
  }

  function removeDefault(): void {
    const updated = { ...sourceRule }
    delete updated.default
    updateRule(updated)
  }

  function removeArtifactEntry(artifactName: string): void {
    const newArtifacts = { ...(sourceRule.on_artifact ?? {}) }
    delete newArtifacts[artifactName]
    const updated: StateRule = { ...sourceRule, on_artifact: newArtifacts }
    if (Object.keys(newArtifacts).length === 0) delete updated.on_artifact
    updateRule(updated)
  }

  function removeContentEntry(idx: number): void {
    const arr = [...(sourceRule.on_content ?? [])]
    arr.splice(idx, 1)
    const updated: StateRule = { ...sourceRule, on_content: arr }
    if (arr.length === 0) delete updated.on_content
    updateRule(updated)
  }

  function removeDecide(): void {
    const updated = { ...sourceRule }
    delete updated.decide
    updateRule(updated)
  }

  function submitAddCondition(): void {
    const type = addCond.type
    if (type === 'default') {
      updateRule({ ...sourceRule, default: target })
    } else if (type === 'on_artifact') {
      const artifactName = addCond.artifact.trim() || 'artifact.md'
      updateRule({
        ...sourceRule,
        on_artifact: { ...(sourceRule.on_artifact ?? {}), [artifactName]: target },
      })
    } else if (type === 'on_content') {
      const entry = { file: addCond.file.trim() || 'notes.md', contains: addCond.contains.trim(), next: target }
      updateRule({
        ...sourceRule,
        on_content: [...(sourceRule.on_content ?? []), entry],
      })
    } else if (type === 'decide') {
      const question = addCond.question.trim() || 'Where next?'
      const optLabel = addCond.optionLabel.trim() || 'approve'
      updateRule({
        ...sourceRule,
        decide: { question, options: { [optLabel]: target }, default: optLabel },
      })
    }
    setAddCond((s) => ({ ...s, open: false }))
  }

  return { addCond, setAddCond, submitAddCondition, removeDefault, removeArtifactEntry, removeContentEntry, removeDecide }
}
