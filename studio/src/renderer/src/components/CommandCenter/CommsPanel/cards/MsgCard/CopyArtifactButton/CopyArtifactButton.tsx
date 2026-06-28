import { useState } from 'react'
import { Copy, Link2, Check } from 'lucide-react'
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
  /** 'content' copies the file's text; 'path' copies the resolved absolute path. */
  kind?: 'content' | 'path'
}

// Copies either the artifact's FILE CONTENT or its absolute PATH to the clipboard.
// Resolves a project-relative path against the project root (same helper the summary/
// preview use). Shows a transient ✓ and a toast.
export function CopyArtifactButton({ path, name, kind = 'content' }: Props): JSX.Element {
  const [copied, setCopied] = useState(false)
  const projectPath = useProjectStore((st) => st.projectPath)

  async function copy(): Promise<void> {
    const toast = useToastStore.getState().push
    const abs = resolveArtifactPath(path, projectPath)
    try {
      if (kind === 'path') {
        await window.pathly.clipboard.write(abs)
        setCopied(true)
        toast(`Copied path: ${name}`, 'success', { category: 'db_crud' })
      } else {
        const text = await readFile(abs)
        if (text == null) {
          toast(`Could not read ${name}`, 'error', { category: 'db_crud' })
          return
        }
        await window.pathly.clipboard.write(text)
        setCopied(true)
        toast(`Copied ${name} to clipboard`, 'success', { category: 'db_crud' })
      }
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast(`Could not copy ${kind === 'path' ? 'path' : name}`, 'error', { category: 'db_crud' })
    }
  }

  const tip = kind === 'path' ? 'Copy file path' : 'Copy artifact to clipboard'
  const Icon = kind === 'path' ? Link2 : Copy

  return (
    <button
      type="button"
      className={s.copyBtn}
      title={tip}
      aria-label={tip}
      onClick={() => { void copy() }}
    >
      {copied ? <Check size={12} /> : <Icon size={12} />}
    </button>
  )
}
