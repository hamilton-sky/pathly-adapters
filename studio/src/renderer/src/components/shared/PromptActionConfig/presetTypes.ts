export interface PromptPreset {
  name: string
  label: string
  hint: string
  prompt: string
  skillRef?: string
}

/**
 * Replace every {{KEY}} placeholder with vars[KEY].
 * Tokens with no matching key are left untouched.
 */
export function resolvePrompt(template: string, vars: Record<string, string>): string {
  return template.replace(/\{\{([^}]+)\}\}/g, (match, key: string) =>
    Object.prototype.hasOwnProperty.call(vars, key) ? vars[key] : match,
  )
}
