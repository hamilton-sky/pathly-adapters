import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { useProjectStore } from '../../../../../../store/projectStore'
import { useToastStore } from '../../../../../../store/toastStore'
import { readFile } from '../../../../../../services/pathlyApi'
import { resolveArtifactPath } from '../../../artifactPath'
import s from './CopyArtifactButton.module.css'

interface Props {
  /** The artifact file path (project-relative or absolute). */
  path: string
  /** Display name, used in the confirmation toast. */
  name: string
}

// Copies the artifact's FILE CONTENT to the clipboard. Resolves a project-relative path
// against the project root (same helper the summary/preview use), reads the file, and
// writes it via the clipboard IPC. Shows a transient ✓ and a toast.
export function CopyArtifactButton({ path, name }: Props): JSX.Element {
  const [copied, setCopied] = useState(false)
  const projectPath = useProjectStore((st) => st.projectPath)

  async function copy(): Promise<void> {
    const toast = useToastStore.getState().push
    try {
      const text = await readFile(resolveArtifactPath(path, projectPath))
      if (text == null) {
        toast(`Could not read ${name}`, 'error', { category: 'db_crud' })
        return
      }
      await window.pathly.clipboard.write(text)
      setCopied(true)
      toast(`Copied ${name} to clipboard`, 'success', { category: 'db_crud' })
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast(`Could not copy ${name}`, 'error', { category: 'db_crud' })
    }
  }

  return (
    <button
      type="button"
      className={s.copyBtn}
      title="Copy artifact to clipboard"
      aria-label="Copy artifact to clipboard"
      onClick={() => { void copy() }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  )
}
