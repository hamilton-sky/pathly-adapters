import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { useToastStore } from '../../../store/toastStore'
import { Tooltip } from '../../ui'
import s from './CopyTextButton.module.css'

interface Props {
  /** The in-memory text copied to the clipboard. */
  text: string
  /** Human label for the tooltip / toast, e.g. "AI Summary". */
  label: string
}

/**
 * Small icon button that copies an in-memory string to the clipboard, showing a
 * transient ✓ and a toast. Generic counterpart to CopyArtifactButton, which
 * reads its text from a file path instead.
 */
export function CopyTextButton({ text, label }: Props): JSX.Element {
  const [copied, setCopied] = useState(false)

  async function copy(): Promise<void> {
    const toast = useToastStore.getState().push
    try {
      await window.pathly.clipboard.write(text)
      setCopied(true)
      toast(`Copied ${label} to clipboard`, 'success', { category: 'db_crud' })
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast(`Could not copy ${label}`, 'error', { category: 'db_crud' })
    }
  }

  const tip = `Copy ${label}`
  return (
    <Tooltip label={tip} placement="top">
      <button
        type="button"
        className={s.copyBtn}
        aria-label={tip}
        onClick={(e) => { e.stopPropagation(); void copy() }}
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </Tooltip>
  )
}
