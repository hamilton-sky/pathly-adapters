import { useEffect, useState } from 'react'

// Feature slugs for the current project — powers the New-run Scope dropdown so the user picks an
// existing feature instead of typing a slug. Best-effort: [] until GET /db/features responds / on
// error (the form then falls back to the free-text scope input).
export function useProjectFeatures(projectRoot: string): string[] {
  const [features, setFeatures] = useState<string[]>([])

  useEffect(() => {
    let alive = true
    void window.pathly.db
      .features(projectRoot || undefined)
      .then((rows) => {
        if (!alive) return
        const slugs = Array.from(
          new Set((rows ?? []).map((r) => r.feature).filter((f): f is string => !!f)),
        ).sort()
        setFeatures(slugs)
      })
      .catch(() => {
        /* leave empty → free-text fallback */
      })
    return () => {
      alive = false
    }
  }, [projectRoot])

  return features
}
