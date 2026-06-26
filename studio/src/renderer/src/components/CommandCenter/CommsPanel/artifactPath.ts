// Shared artifact-path resolution. Agents post PROJECT-RELATIVE paths (e.g.
// `pathly/plans/foo/APPROACH.md`), but the fs:read IPC does NOT resolve them — it
// passes the string straight to fs.readFileSync, which resolves a relative path
// against the Electron main-process CWD (not the project root) and gets ENOENT.
// Every consumer that reads a stored artifact path must funnel through here so a
// relative path becomes absolute against the project root before the read.

/**
 * Resolve a possibly-relative artifact path to absolute against the project root.
 * Already-absolute paths (Windows drive `C:\`/`C:/`, POSIX `/`, or UNC `\\`) pass
 * through unchanged. Returns the input verbatim when there is no root to join to.
 */
export function resolveArtifactPath(p: string, root: string | null | undefined): string {
  if (/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(p)) return p
  const base = (root ?? '').replace(/[\\/]+$/, '')
  return base ? `${base}/${p.replace(/^[\\/]+/, '')}` : p
}
