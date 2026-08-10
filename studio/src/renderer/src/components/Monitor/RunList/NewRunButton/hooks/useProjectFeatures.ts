import { useEffect, useState } from 'react'
import { listDirs } from '../../../../../services/pathlyApi'

// Feature slugs for the New-run Scope dropdown. Sourced from the ON-DISK feature folders
// (pathly/features/*) — the COMPLETE set the CommandCenter itself lists — MERGED with any DB-only
// features (a run whose folder was archived/removed). db.features ALONE is incomplete: it only
// returns features that have DB activity (invocations/state), so a fresh feature folder with no
// runs yet would be missing. Excludes `.archive` + hidden dirs. Best-effort → [] on error.
export function useProjectFeatures(projectRoot: string): string[] {
  const [features, setFeatures] = useState<string[]>([])

  useEffect(() => {
    if (!projectRoot) {
      setFeatures([])
      return
    }
    let alive = true
    void Promise.all([
      listDirs(`${projectRoot}/pathly/features`).catch(() => [] as string[]),
      window.pathly.db
        .features(projectRoot)
        .then((rows) => (rows ?? []).map((r) => r.feature))
        .catch(() => [] as string[]),
    ]).then(([disk, db]) => {
      if (!alive) return
      const slugs = Array.from(new Set([...disk, ...db]))
        .filter((f): f is string => !!f && !f.startsWith('.'))
        .sort()
      setFeatures(slugs)
    })
    return () => {
      alive = false
    }
  }, [projectRoot])

  return features
}
