export interface Transition {
  from: string
  to: string
  label: string
}

export interface Props {
  onClose: () => void
  onCreated: (filePath: string) => void
}
