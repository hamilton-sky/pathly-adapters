import { FileText } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { CommsMsgCard } from '../CommsMsgCard'
import s from './ArtifactsView.module.css'

interface Props {
  messages: Message[]
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
}

// The "Artifacts" board view: type='artifact' messages as a filtered card list,
// reusing the existing artifact card (CommsMsgCard → CardBody artifact branch +
// the Details/ArtifactModal plumbing).
export function ArtifactsView({ messages, onDelete, onSupersede }: Props): JSX.Element {
  const artifacts = messages.filter((m) => m.type === 'artifact')

  if (artifacts.length === 0) {
    return (
      <div className={s.empty}>
        <FileText size={22} />
        <p>No artifacts on this board yet.</p>
      </div>
    )
  }

  return (
    <div className={s.view}>
      {artifacts.map((m) => (
        <CommsMsgCard
          key={m.id}
          message={m}
          flash={false}
          onDelete={onDelete}
          onSupersede={onSupersede}
          siblings={messages}
        />
      ))}
    </div>
  )
}
