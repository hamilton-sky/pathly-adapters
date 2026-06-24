import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../../../lib/config'
import { useToastStore } from '../../../../store/toastStore'

const SETTING_KEY = 'pathly.auto_commit'

function isEnabled(value: string | undefined): boolean {
  if (!value) return false
  return ['true', '1', 'yes', 'on'].includes(value.toLowerCase())
}

export function useAutoCommitSetting(): { enabled: boolean; toggle: () => void } {
  const [enabled, setEnabled] = useState(false)
  const pushToast = useToastStore((s) => s.push)

  useEffect(() => {
    apiFetch('/db/settings')
      .then((r) => r.json() as Promise<Record<string, string>>)
      .then((settings) => setEnabled(isEnabled(settings[SETTING_KEY])))
      .catch(() => {/* keep default OFF on fetch failure */})
  }, [])

  const toggle = useCallback(() => {
    const next = !enabled
    setEnabled(next)
    apiFetch(`/db/settings/${SETTING_KEY}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: next ? 'true' : 'false' }),
    }).catch(() => {
      setEnabled(!next)
      pushToast('Failed to save auto-commit setting', 'error')
    })
  }, [enabled, pushToast])

  return { enabled, toggle }
}
