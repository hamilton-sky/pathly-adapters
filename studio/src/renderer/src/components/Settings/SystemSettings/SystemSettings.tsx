import { ExportSettings } from '../ExportSettings'
import { NotificationSettings } from '../NotificationSettings'

// Operational/system preferences: artifact export defaults + desktop notifications.
export function SystemSettings(): JSX.Element {
  return (
    <>
      <ExportSettings />
      <NotificationSettings />
    </>
  )
}
