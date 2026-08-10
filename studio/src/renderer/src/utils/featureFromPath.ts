/**
 * Extract the feature slug from a path under `pathly/features/<slug>/…` (any OS separators), or
 * undefined when the path isn't inside a feature dir. Used to attribute renderer one-shots (editor
 * Split/Analyze/Diagram/Comment + artifact summaries) to the board they act on — so they key to
 * that feature in the Pipeline (GET /runs) instead of the generic `(project)`. A non-feature file
 * (e.g. a loose doc) has no feature → the run stays `(project)`, which is correct.
 */
export function featureFromPath(path: string | undefined | null): string | undefined {
  if (!path) return undefined
  const m = /[/\\]pathly[/\\]features[/\\]([^/\\]+)/.exec(path)
  return m ? m[1] : undefined
}
